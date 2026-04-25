"""
Training script for ATC RL Environment using Huggingface TRL (PPO) and PEFT (LoRA).
Designed to be run in a GPU-enabled environment (like Google Colab).
"""

import os
import torch
import math
import sys
from typing import Optional

from transformers import AutoTokenizer, AutoConfig, BitsAndBytesConfig
from peft import LoraConfig
from trl import AutoModelForCausalLMWithValueHead, PPOConfig, PPOTrainer

from rl_env.environment import ATCEnv
from rl_env.models import ATCAction
from rl_env.prompts.atc_prompt import generate_atc_prompt
from rl_env.parsers import parse, ParseError

# Re-use structures, prompts, and config from inference.py
from inference import (
    SYSTEM_PROMPT,
    build_commands_from_response,
    log_start,
    log_step,
    log_end,
    normalize_score,
    MAX_STEPS_PER_EPISODE,
    SUCCESS_SCORE_THRESHOLD,
    BENCHMARK_NAME,
    TASKS,
)

# ---------------------------------------------------------------------------
# Training Episode Runner
# ---------------------------------------------------------------------------

def run_training_episode(
    env: ATCEnv,
    ppo_trainer: PPOTrainer,
    tokenizer: AutoTokenizer,
    task_name: str,
) -> tuple[bool, int, float, list[float], dict]:
    
    device = ppo_trainer.accelerator.device
    model_name_for_logging = ppo_trainer.config.model_name
    
    rewards: list[float] = []
    queries: list[torch.Tensor] = []
    responses: list[torch.Tensor] = []
    
    steps_taken = 0
    success = False
    score = 0.0

    log_start(task=task_name, env=BENCHMARK_NAME, model=model_name_for_logging)

    try:
        observation, _info = env.reset(task=task_name)

        consecutive_errors = 0

        try:
            for step_num in range(1, MAX_STEPS_PER_EPISODE + 1):
                steps_taken = step_num

                # Exact same prompt as inference
                prompt = generate_atc_prompt(observation)
                
                # Format to match the conversational structure in inference
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ]
                text_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                # Keep prompt tensor 1D
                prompt_tensor = tokenizer(text_prompt, return_tensors="pt").input_ids[0].to(device)

                # Generate response exactly like getting an LLM response
                generation_kwargs = {
                    "min_length": -1,
                    "top_k": 0.0,
                    "top_p": 1.0,
                    "do_sample": True,
                    "pad_token_id": tokenizer.pad_token_id,
                    "max_new_tokens": 128,
                }
                
                response_tensors = ppo_trainer.generate([prompt_tensor], **generation_kwargs)
                response_tensor = response_tensors[0][prompt_tensor.shape[0]:] # Only the generated sequence
                
                llm_text = tokenizer.decode(response_tensor, skip_special_tokens=True).strip()

                # Reuse parser
                commands, parse_error = build_commands_from_response(llm_text)
                action = ATCAction(commands=commands)
                action_str = "; ".join(commands) if commands else "NOOP"

                try:
                    observation, reward, done, _truncated, _info = env.step(action)
                    
                    # Optional: Add penalty for failing to parse into PPO reward
                    if parse_error:
                        reward -= 0.5
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 0

                    rewards.append(reward)
                    queries.append(prompt_tensor)
                    responses.append(response_tensor)

                    log_step(
                        step=step_num,
                        action=action_str,
                        reward=reward,
                        done=done,
                        error=parse_error,
                    )

                    if done:
                        break

                    # Early termination logic for stagnating models
                    if consecutive_errors >= 5:
                        print(f"\n[Early Stop] 5 consecutive parse errors.", file=sys.stderr, flush=True)
                        break

                    if reward <= -2.0:
                        print(f"\n[Early Stop] Extreme negative reward ({reward:.2f}).", file=sys.stderr, flush=True)
                        break

                except Exception as exc:
                    rewards.append(-1.0) # Penalty for breaking env
                    queries.append(prompt_tensor)
                    responses.append(response_tensor)
                    log_step(
                        step=step_num,
                        action=action_str,
                        reward=-1.0,
                        done=True,
                        error=f"step_error:{exc}",
                    )
                    break

        except Exception as exc:
            if steps_taken == 0:
                steps_taken = 1
            rewards.append(0.0)
            log_step(
                step=steps_taken,
                action="ERROR",
                reward=0.0,
                done=True,
                error=f"episode_error:{exc}",
            )

    finally:
        try:
            env.close()
        except Exception:
            pass

    return success, steps_taken, score, rewards, {}

# ---------------------------------------------------------------------------
# Main Training Loop
# ---------------------------------------------------------------------------

def main() -> None:
    # We use Google's Gemma by default just as defined in inference.py 
    # Use 2b for training as it's easier to fit on standard GPUs
    model_name = os.getenv("MODEL_NAME", "google/gemma-3n-E4B-it")
    epochs = int(os.getenv("EPOCHS", "10"))
    
    print(f"Loading configuration for PPO + LoRA on `{model_name}`...", file=sys.stderr, flush=True)

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    
    ppo_config = PPOConfig(
        model_name=model_name,
        learning_rate=1e-5,
        batch_size=2,
        mini_batch_size=1,
        gradient_accumulation_steps=2,
    )

    print("Loading tokenizer and models (this may take a while)...", file=sys.stderr, flush=True)
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    except Exception as e:
        print(f"Fast tokenizer failed to load ({e}). Falling back to slow tokenizer...", file=sys.stderr, flush=True)
        # Often happens with newer Gemma architectures if `transformers` or `tokenizers` library is outdated.
        tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False, trust_remote_code=True)
        
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # --- Custom Config Patch for TRL / Gemma 3 ---
    # TRL's ValueHead expects 'hidden_size' but custom architectures often bury it 
    # under different variable names, resulting in an UnboundLocalError.
    print("Loading config and patching for TRL...", file=sys.stderr, flush=True)
    try:
        config = AutoConfig.from_pretrained(ppo_config.model_name, trust_remote_code=True)
        if not hasattr(config, "hidden_size"):
            # Attempt to map from text_config for multimodal models like Gemma 3
            if hasattr(config, "text_config") and hasattr(config.text_config, "hidden_size"):
                patched_size = config.text_config.hidden_size
            else:
                # Fallback to alternate names or 2048 (default for Gemma 3 4B)
                patched_size = getattr(config, "model_dim", getattr(config, "d_model", getattr(config, "n_embd", 2048)))
            config.hidden_size = patched_size
            print(f"Patched config.hidden_size to {patched_size}", file=sys.stderr, flush=True)
    except Exception as exc:
        print(f"Warning: Failed to load/patch config: {exc}", file=sys.stderr, flush=True)
        config = None

    # QLoRA 4-bit Quantization to fit 4B parameters perfectly onto a 16GB Colab T4
    print("Initializing 4-bit BitsAndBytes quantization...", file=sys.stderr, flush=True)
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )

    # Active Policy Model
    try:
        model = AutoModelForCausalLMWithValueHead.from_pretrained(
            ppo_config.model_name,
            config=config,
            peft_config=lora_config,
            quantization_config=quantization_config,
            device_map="cuda",  # Force to GPU strictly, prevent CPU offloading!
            trust_remote_code=True
        )
    except Exception as exc:
        print(f"FATAL: Failed to initialize Policy model: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
        
    print("Enabling gradient checkpointing...", file=sys.stderr, flush=True)
    if hasattr(model.pretrained_model, "gradient_checkpointing_enable"):
        model.pretrained_model.config.use_cache = False
        model.pretrained_model.gradient_checkpointing_enable()
    
    ppo_trainer = PPOTrainer(
        config=ppo_config,
        model=model,
        ref_model=None, # TRL will automatically use the un-adapted PEFT base model to compute KL!
        tokenizer=tokenizer,
    )

    print(f"PPOTrainer ready. Using device: {ppo_trainer.accelerator.device}", file=sys.stderr, flush=True)

    try:
        env = ATCEnv()
    except Exception as exc:
        print(f"FATAL: Failed to initialize ATCEnv: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Run Training
    # -----------------------------------------------------------------------
    
    # Accumulators for batch updates
    all_queries = []
    all_responses = []
    all_rewards = []

    for epoch in range(1, epochs + 1):
        print(f"\n=== EPOCH {epoch}/{epochs} ===", file=sys.stderr, flush=True)
        
        successes = 0
        total_score = 0.0

        for task_name in TASKS:
            # We need to manually run the episode step-by-step here to collect 
            # query/response/reward lists for the TRL batch update.
            device = ppo_trainer.accelerator.device
            ep_rewards: list[float] = []
            ep_queries: list[torch.Tensor] = []
            ep_responses: list[torch.Tensor] = []
            
            steps_taken = 0
            score = 0.0
            log_start(task=task_name, env=BENCHMARK_NAME, model=ppo_config.model_name)
            
            observation, _info = env.reset(task=task_name)
            consecutive_errors = 0
            done = False

            for step_num in range(1, MAX_STEPS_PER_EPISODE + 1):
                steps_taken = step_num
                prompt = generate_atc_prompt(observation)
                messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
                text_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                prompt_tensor = tokenizer(text_prompt, return_tensors="pt").input_ids[0].to(device)

                generation_kwargs = {"min_length": -1, "top_k": 0.0, "top_p": 1.0, "do_sample": True, "pad_token_id": tokenizer.pad_token_id, "max_new_tokens": 128}
                response_tensors = ppo_trainer.generate([prompt_tensor], **generation_kwargs)
                response_tensor = response_tensors[0][prompt_tensor.shape[0]:]
                llm_text = tokenizer.decode(response_tensor, skip_special_tokens=True).strip()

                commands, parse_error = build_commands_from_response(llm_text)
                action = ATCAction(commands=commands)
                action_str = "; ".join(commands) if commands else "NOOP"

                try:
                    observation, reward, done, _truncated, _info = env.step(action)
                    if parse_error:
                        reward -= 0.5
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 0

                    ep_rewards.append(reward)
                    ep_queries.append(prompt_tensor)
                    ep_responses.append(response_tensor)

                    log_step(step=step_num, action=action_str, reward=reward, done=done, error=parse_error)
                    if done: break
                    if consecutive_errors >= 5 or reward <= -2.0: break

                except Exception as exc:
                    ep_rewards.append(-1.0)
                    ep_queries.append(prompt_tensor)
                    ep_responses.append(response_tensor)
                    log_step(step=step_num, action=action_str, reward=-1.0, done=True, error=f"step_error:{exc}")
                    done = True
                    break

            score = normalize_score(sum(ep_rewards), steps_taken)
            if score >= SUCCESS_SCORE_THRESHOLD: successes += 1
            total_score += score
            log_end(success=(score >= SUCCESS_SCORE_THRESHOLD), steps=steps_taken, score=score, rewards=ep_rewards)

            # Move episode data to batch accumulators
            all_queries.extend(ep_queries)
            all_responses.extend(ep_responses)
            all_rewards.extend([torch.tensor(r, dtype=torch.float, device=device) for r in ep_rewards])

            # Trigger PPO update only when we have a full batch
            while len(all_queries) >= ppo_config.batch_size:
                curr_queries = all_queries[:ppo_config.batch_size]
                curr_responses = all_responses[:ppo_config.batch_size]
                curr_rewards = all_rewards[:ppo_config.batch_size]
                
                all_queries = all_queries[ppo_config.batch_size:]
                all_responses = all_responses[ppo_config.batch_size:]
                all_rewards = all_rewards[ppo_config.batch_size:]
                
                # Clear VRAM before the expensive PPO forward/backward passes
                import gc
                gc.collect()
                torch.cuda.empty_cache()
                
                stats = ppo_trainer.step(curr_queries, curr_responses, curr_rewards)
                ppo_loss = stats.get("ppo/loss/total", 0.0)
                print(f"  -> Batch Update: PPO Loss={ppo_loss:.4f}", file=sys.stderr, flush=True)

        avg_score = total_score / len(TASKS) if TASKS else 0.0
        print(f"\n--- Epoch {epoch} Summary ---", file=sys.stderr, flush=True)
        print(f"Tasks completed: {successes}/{len(TASKS)}", file=sys.stderr, flush=True)
        print(f"Average score:   {avg_score:.2f}", file=sys.stderr, flush=True)

        print(f"Total score:     {total_score:.2f}", file=sys.stderr, flush=True)
        
        # -----------------------------------------------------------------------
        # Save Intermediate Checkpoint
        # -----------------------------------------------------------------------
        checkpoint_dir = f"./atc_rl_lora_model_epoch_{epoch}"
        print(f"Saving checkpoint to {checkpoint_dir}...", file=sys.stderr, flush=True)
        model.save_pretrained(checkpoint_dir)
        tokenizer.save_pretrained(checkpoint_dir)

    # -----------------------------------------------------------------------
    # Save Final Model Weights
    # -----------------------------------------------------------------------
    out_dir = "./atc_rl_lora_model_final"
    print(f"\nTraining completed. Saving final adapter and tokenizer to {out_dir}...", file=sys.stderr, flush=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    print("Done!", file=sys.stderr, flush=True)

if __name__ == "__main__":
    main()

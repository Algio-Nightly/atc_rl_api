"""
Training script for ATC RL Environment using Huggingface TRL (PPO) and PEFT (LoRA).
Designed to be run in a GPU-enabled environment (like Google Colab).
"""

import os
import torch
import math
import sys
from typing import Optional

from transformers import AutoTokenizer
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

    score = normalize_score(sum(rewards), steps_taken)
    success = score >= SUCCESS_SCORE_THRESHOLD

    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    
    # Run PPO Update Step
    stats = {}
    if queries:
        # Convert rewards list to list of tensors for TRL
        reward_tensors = [torch.tensor(r, dtype=torch.float, device=device) for r in rewards]
        stats = ppo_trainer.step(queries, responses, reward_tensors)
        
    return success, steps_taken, score, rewards, stats

# ---------------------------------------------------------------------------
# Main Training Loop
# ---------------------------------------------------------------------------

def main() -> None:
    # We use Google's Gemma by default just as defined in inference.py 
    # Use 2b for training as it's easier to fit on standard GPUs
    model_name = os.getenv("MODEL_NAME", "google/gemma-2b-it")
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
        batch_size=8,
        mini_batch_size=4,
        gradient_accumulation_steps=2,
    )

    print("Loading tokenizer and models (this may take a while)...", file=sys.stderr, flush=True)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Active Policy Model
    try:
        model = AutoModelForCausalLMWithValueHead.from_pretrained(
            ppo_config.model_name,
            peft_config=lora_config,
            device_map="auto"
        )
    except Exception as exc:
        print(f"FATAL: Failed to initialize Policy model: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
    
    # Reference Model (Keep frozen for KL divergence)
    try:
        ref_model = AutoModelForCausalLMWithValueHead.from_pretrained(
            ppo_config.model_name,
            peft_config=lora_config,
            device_map="auto"
        )
    except Exception as exc:
        print(f"FATAL: Failed to initialize Reference model: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)

    ppo_trainer = PPOTrainer(
        config=ppo_config,
        model=model,
        ref_model=ref_model,
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
    for epoch in range(1, epochs + 1):
        print(f"\n=== EPOCH {epoch}/{epochs} ===", file=sys.stderr, flush=True)
        
        successes = 0
        total_score = 0.0

        for task_name in TASKS:
            ok, steps, score, episode_rewards, stats = run_training_episode(
                env=env,
                ppo_trainer=ppo_trainer,
                tokenizer=tokenizer,
                task_name=task_name
            )
            if ok:
                successes += 1
            total_score += score
            
            ppo_loss = stats.get("ppo/loss/total", 0.0)
            mean_reward = sum(episode_rewards) / max(1, len(episode_rewards))
            print(f"  -> Task '{task_name}': Score={score:.2f}, Mean Reward={mean_reward:.2f}, PPO Loss={ppo_loss:.4f}", file=sys.stderr, flush=True)

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

import React, { useState, useEffect, useRef } from 'react';

export default function DevConsole({ actions, onSendCommand }) {
  const [cmd, setCmd] = useState("");
  const logEndRef = useRef(null);

  // Auto-scroll to bottom of logs
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [actions]);

  const handleSend = () => {
    if (cmd.trim()) {
      if (onSendCommand) {
        onSendCommand(cmd);
      } else {
        console.log("Sending command to backend:", cmd);
      }
      setCmd("");
    }
  };

  const formatEvent = (act) => {
    if (typeof act === 'string') return act;
    const type = act.type || "INFO";
    const body = act.msg || act.message || JSON.stringify(act);
    const preview = typeof body === 'string' && body.length > 240 ? `${body.slice(0, 240)}…` : body;
    
    // Custom formatting for specific types
    if (type === "SPAWN") return `[SPAWN] ${act.callsign} (${act.weight_class} ${act.ac_type}) entered airspace`;
    if (type === "LANDING") return `[LAND] ${act.callsign} landed successfully (+${act.reward})`;
    if (type === "CRASH") return `[CRASH] ${act.callsign} !! CRITICAL SEPARATION LOSS !!`;
    if (type === "RUNWAY_CHANGE") return `[RWY] Selection changed to: ${act.to?.join(', ')}`;
    if (type === "WAYPOINT_CREATED") return `[INFRA] New waypoint created: ${act.name}`;
    if (type === "RUNWAY_CREATED") return `[INFRA] New runway created: ${act.id}`;
    if (type === "AIRPORT_CREATED") return `[INFRA] New airport created: ${act.name} (${act.code})`;
    if (type === "ATC") return `[ATC] ${body}`;
    if (type === "ERROR") return `[ERROR] !! ${body} !!`;
    if (type === "INFO" && body.startsWith("CMD:")) return `[SIM] ${body.replace("CMD: ", "")}`;
    if (type === "RL_TASK") return `[RL] ${act.phase || 'step'} task=${act.task} model=${act.model} step=${act.step}`;
    if (type === "RL_PROMPT") return `[PROMPT] ${preview}`;
    if (type === "RL_RESPONSE") return `[MODEL] ${preview}`;
    if (type === "RL_ACTION") return `[ACTION] ${act.action}`;
    if (type === "RL_REWARD") return `[REWARD] step=${act.step} reward=${act.reward} cumulative=${act.cumulative_reward} done=${act.done}`;
    if (type === "RL_ERROR") return `[RL ERROR] ${body}`;
    
    return `[${type}] ${body}`;
  };

  return (
    <div className="console-panel" style={{ display: 'flex', flexDirection: 'column' }}>
      <h3 style={{ margin: '0 0 8px 0' }}>Live Simulation Log</h3>

      <div style={{ 
        flex: 1,
        background: '#0a0a0a', 
        color: '#00ff00', 
        padding: '12px', 
        fontFamily: 'monospace', 
        fontSize: '0.85rem',
        overflowY: 'auto',
        borderRadius: '4px',
        border: '1px solid #333',
        boxShadow: 'inset 0 0 10px rgba(0,0,0,1)'
      }}>
        {actions.map((act, i) => {
          const timestamp = act.timestamp 
            ? new Date(act.timestamp * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})
            : new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
            
          const isError = act.type === "ERROR";
          const isATC = act.type === "ATC";
          
          return (
            <div key={act.timestamp || i} style={{ 
              marginBottom: '4px', 
              borderLeft: `2px solid ${isError ? '#ff0000' : isATC ? '#007bff' : '#004400'}`, 
              paddingLeft: '8px',
              color: isError ? '#ffaaaa' : isATC ? '#aaaaff' : '#00ff00'
            }}>
              <span style={{ color: isError ? '#ff5555' : isATC ? '#5555ff' : '#008800', marginRight: '8px' }}>[{timestamp}]</span>
              {formatEvent(act)}
            </div>
          );
        })}
        <div ref={logEndRef} />
      </div>

      <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
        <input
          type="text"
          value={cmd}
          onChange={e => setCmd(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleSend(); }}
          placeholder="Enter SIM/ATC Command..."
          style={{ 
            flex: 1, 
            padding: '8px', 
            background: '#1a1a1a', 
            color: '#fff', 
            border: '1px solid #444',
            borderRadius: '4px'
          }}
        />
        <button className="btn" onClick={handleSend} style={{ padding: '8px 20px' }}>EXEC</button>
      </div>
    </div>
  );
}

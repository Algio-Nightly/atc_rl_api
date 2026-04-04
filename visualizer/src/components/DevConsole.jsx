import React, { useState } from 'react';

export default function DevConsole({ actions, onSendCommand }) {
  const [cmd, setCmd] = useState("");

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

  return (
    <div className="console-panel">
      <h3>Dev Console</h3>
      
      <div style={{ marginTop: '16px', background: '#222', color: '#0f0', padding: '8px', fontFamily: 'monospace', height: '100px', overflowY: 'auto' }}>
        {actions.map((act, i) => (
          <div key={i}>
            {typeof act === 'string' ? act : (act.msg || act.message || JSON.stringify(act))}
          </div>
        ))}
      </div>
      
      <div style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
        <input 
          type="text" 
          value={cmd} 
          onChange={e => setCmd(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleSend(); }} 
          placeholder="Type slash commands (e.g. /spawn-storm) or raw JSON..." 
          style={{ flex: 1, padding: '4px' }}
        />
        <button className="btn" onClick={handleSend}>Send</button>
      </div>
    </div>
  );
}

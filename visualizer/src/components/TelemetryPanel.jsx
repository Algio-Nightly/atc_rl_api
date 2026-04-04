import React from 'react';

export default function TelemetryPanel({ gameState }) {
  return (
    <div className="header-panel">
      <div>
        <h3>ATC Telemetry</h3>
      </div>
      <div style={{ display: 'flex', gap: '24px' }}>
        <div><strong>Reward:</strong> {gameState.reward}</div>
        <div><strong>Step:</strong> {gameState.step}</div>
        <div><strong>Landed:</strong> {gameState.landed}</div>
        <div><strong>Violations:</strong> {gameState.violations}</div>
        <div><strong>Wind:</strong> {gameState.wind}</div>
        <div><strong>Runway:</strong> {gameState.runwayStatus}</div>
      </div>
    </div>
  );
}

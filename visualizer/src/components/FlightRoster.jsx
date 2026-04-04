import React from 'react';

export default function FlightRoster({ flights, onSelectFlight, gameState }) {
  return (
    <div className="sidebar-panel">
      {gameState && (
        <div style={{ marginBottom: '24px', paddingBottom: '16px', borderBottom: '1px solid #ccc' }}>
          <h3>Environment</h3>
          <div style={{ fontSize: '0.9rem', marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div><strong>Sim Time:</strong> {gameState.simulation_time?.toFixed(2)}</div>
            <div><strong>Wind:</strong> {gameState.wind_heading}° @ {gameState.wind_speed}kts</div>
            <div><strong>Runway:</strong> {gameState.active_runway}</div>
            <div><strong>Time Scale:</strong> {gameState.time_scale}x</div>
          </div>
        </div>
      )}

      <h3>Active Flights</h3>
      <div style={{ marginTop: '16px' }}>
        {flights.map((flight) => (
          <div 
            key={flight.callsign} 
            className="flight-item"
            onClick={() => onSelectFlight(flight)}
          >
            <strong>{flight.callsign} ({flight.type})</strong>
            <div style={{ fontSize: '0.9rem', color: '#666', marginTop: '4px' }}>
              Status: {flight.state} | Fuel: {flight.fuel_level?.toFixed(1)}%
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

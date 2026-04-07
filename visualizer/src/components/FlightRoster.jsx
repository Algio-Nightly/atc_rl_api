import React from 'react';
import { MAP_CENTER } from '../utils/geo';

export default function FlightRoster({ flights, onSelectFlight, gameState, sendWSMessage, hoveredWaypoint }) {
  return (
    <div className="sidebar-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {gameState && (
          <div style={{ marginBottom: '24px', paddingBottom: '16px', borderBottom: '1px solid #eee' }}>
            <h3 style={{ fontSize: '0.75rem', color: '#555', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Environment</h3>
            <div style={{ fontSize: '0.85rem', marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px', color: '#1a1a1a' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Sim Time:</span> <span style={{ fontWeight: '600' }}>{gameState.simulation_time?.toFixed(1)}s</span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Wind:</span> <span style={{ fontWeight: '600' }}>{gameState.wind_heading}° @ {gameState.wind_speed}kts</span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Active RWY:</span> <span style={{ color: '#28a745', fontWeight: 'bold' }}>{(gameState.active_runways && gameState.active_runways.length > 0) ? gameState.active_runways.join(', ') : 'NONE'}</span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Time Scale:</span> <span style={{ color: '#007bff', fontWeight: 'bold' }}>{gameState.time_scale}x</span></div>
            </div>
          </div>
        )}

        <h3 style={{ fontSize: '0.75rem', color: '#555', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Active Flights ({flights.length})</h3>
        <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {flights.map((flight) => (
            <div
              key={flight.callsign}
              className="flight-item"
              style={{
                position: 'relative',
                padding: '12px',
                background: '#fcfcfc',
                border: '1px solid #dee2e6',
                borderRadius: '8px',
                cursor: 'pointer',
                transition: 'all 0.2s',
                boxShadow: '0 2px 4px rgba(0,0,0,0.02)'
              }}
              onClick={() => onSelectFlight(flight)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <strong style={{ color: '#1a1a1a', fontSize: '0.95rem' }}>{flight.callsign} <span style={{ fontWeight: 'normal', color: '#6c757d', fontSize: '0.75rem' }}>{flight.type}</span></strong>
                <button
                  title="Remove Aircraft"
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#dc3545',
                    cursor: 'pointer',
                    fontSize: '1.2rem',
                    padding: '0 4px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    opacity: 0.7
                  }}
                  onMouseOver={(e) => e.target.style.opacity = 1}
                  onMouseOut={(e) => e.target.style.opacity = 0.7}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (sendWSMessage) {
                      sendWSMessage('delete_aircraft', { callsign: flight.callsign });
                    }
                  }}
                >×</button>
              </div>
              <div style={{ fontSize: '0.8rem', color: '#495057', marginTop: '6px' }}>
                Alt: {flight.altitude}ft | Spd: {flight.speed}kts
              </div>
              <div style={{ fontSize: '0.75rem', color: flight.state === 'APPROACH' ? '#28a745' : '#6c757d', marginTop: '4px', fontWeight: '500' }}>
                {flight.state}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Waypoint Inspector (Bottom Sticky) */}
      <div style={{
        marginTop: 'auto',
        paddingTop: '16px',
        borderTop: '2px solid #007bff',
        background: hoveredWaypoint ? '#f0f7ff' : '#fafafa',
        padding: '16px',
        borderRadius: '8px',
        transition: 'all 0.3s ease'
      }}>
        <h3 style={{ fontSize: '0.75rem', color: '#0056b3', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>Waypoint Inspector</h3>
        {hoveredWaypoint ? (
          <div style={{ marginTop: '12px', fontSize: '0.85rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <div style={{ gridColumn: 'span 2', fontWeight: 'bold', fontSize: '1rem', color: '#333' }}>{hoveredWaypoint.name}</div>
            <div style={{ color: '#666' }}>Target Alt:</div> <div style={{ fontWeight: '600' }}>{hoveredWaypoint.target_alt} ft</div>
            <div style={{ color: '#666' }}>Target Spd:</div> <div style={{ fontWeight: '600' }}>{hoveredWaypoint.target_speed} kts</div>
            <div style={{ color: '#666' }}>Position X:</div> <div style={{ fontWeight: '600' }}>{hoveredWaypoint.x.toFixed(2)} km</div>
            <div style={{ color: '#666' }}>Position Y:</div> <div style={{ fontWeight: '600' }}>{hoveredWaypoint.y.toFixed(2)} km</div>
            {hoveredWaypoint.is_iaf && (
              <div style={{ gridColumn: 'span 2', marginTop: '4px', color: '#4B0082', fontWeight: 'bold', fontSize: '0.7rem' }}>
                ✦ FINAL APPROACH FIX (IAF)
              </div>
            )}
          </div>
        ) : (
          <div style={{ marginTop: '12px', fontSize: '0.8rem', color: '#999', fontStyle: 'italic' }}>
            Hover over a waypoint on the map for details...
          </div>
        )}
      </div>
    </div>
  );
}

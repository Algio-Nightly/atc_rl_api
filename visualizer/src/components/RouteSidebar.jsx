import React from 'react';

const RouteSidebar = ({ gameState }) => {
  const config = gameState.config;
  // Use config.airport_code to identify the currently active simulation airport
  if (!config || !config.airport_code) {
    return (
      <div className="route-sidebar empty">
        <div className="no-data-msg">Select an airport to view procedural routes</div>
      </div>
    );
  }

  const stars = config.stars || {};
  const sids = config.sids || {};
  const starNames = config.star_names || {};
  const sidNames = config.sid_names || {};

  return (
    <div className="route-sidebar">
      <div className="sidebar-header">
        <h3>{config.airport_code} Procedures</h3>
      </div>
      
      <div className="route-section">
        <h4 className="arrival-label">ARRIVALS (STARs)</h4>
        {Object.entries(stars).map(([gate, gateStars]) => (
          <div key={gate} className="gate-group">
            {Object.entries(gateStars).map(([runway, sequence]) => {
              const name = starNames[`${gate}:${runway}`] || `${gate} \u2192 ${runway}`;
              return (
                <div key={runway} className="route-card star">
                  <div className="route-header">
                    <span className="route-name">{name}</span>
                    <span className="route-tag">STAR</span>
                  </div>
                  <div className="route-meta">{gate} to RWY {runway}</div>
                  <div className="route-sequence">
                    {sequence.map(id => config.waypoints[id]?.name || id).join(' \u2192 ')}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
        {Object.keys(stars).length === 0 && <div className="no-routes">No STARs defined</div>}
      </div>

      <div className="route-section">
        <h4 className="departure-label">DEPARTURES (SIDs)</h4>
        {Object.entries(sids).map(([runway, rwySids]) => (
          <div key={runway} className="rwy-group">
            {Object.entries(rwySids).map(([gate, sequence]) => {
              const name = sidNames[`${runway}:${gate}`] || `${runway} \u2192 ${gate}`;
              return (
                <div key={gate} className="route-card sid">
                  <div className="route-header">
                    <span className="route-name">{name}</span>
                    <span className="route-tag">SID</span>
                  </div>
                  <div className="route-meta">RWY {runway} to {gate}</div>
                  <div className="route-sequence">
                    {sequence.map(id => config.waypoints[id]?.name || id).join(' \u2192 ')}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
        {Object.keys(sids).length === 0 && <div className="no-routes">No SIDs defined</div>}
      </div>

      <style jsx>{`
        .route-sidebar {
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          height: 100%;
          background: #fff;
        }
        .sidebar-header h3 { 
          font-size: 1rem; 
          margin-bottom: 12px; 
          color: #1a202c;
          border-bottom: 2px solid #edf2f7;
          padding-bottom: 8px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .route-section { margin-bottom: 20px; }
        h4 { 
          font-size: 0.7rem; 
          font-weight: 800; 
          letter-spacing: 1px; 
          margin-bottom: 10px; 
        }
        .arrival-label { color: #3182ce; }
        .departure-label { color: #38a169; }
        
        .route-card {
          background: #ffffff;
          border: 1px solid #e2e8f0;
          border-radius: 6px;
          padding: 12px;
          margin-bottom: 10px;
          transition: transform 0.1s;
        }
        .route-card:hover { transform: translateY(-1px); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .route-card.star { border-left: 4px solid #3182ce; }
        .route-card.sid { border-left: 4px solid #38a169; }
        
        .route-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
        .route-name { font-weight: 700; color: #2d3748; font-size: 0.85rem; }
        .route-tag { font-size: 0.6rem; background: #edf2f7; padding: 2px 6px; border-radius: 4px; font-weight: 800; color: #4a5568; }
        .route-meta { font-size: 0.7rem; color: #718096; margin-bottom: 8px; font-weight: 500; }
        .route-sequence { 
          font-size: 0.65rem; 
          color: #4a5568; 
          background: #f7fafc; 
          padding: 6px 10px; 
          border-radius: 4px;
          border: 1px dashed #e2e8f0;
          line-height: 1.4;
        }
        .no-data-msg, .no-routes {
          font-size: 0.8rem;
          color: #a0aec0;
          text-align: center;
          padding: 20px;
          font-style: italic;
        }
      `}</style>
    </div>
  );
};

export default RouteSidebar;

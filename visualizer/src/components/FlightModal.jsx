import React from 'react';

export default function FlightModal({ flight, onClose }) {
  if (!flight) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span>Flight Info: {flight.callsign}</span>
          <button className="btn-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <p><strong>Call Sign:</strong> {flight.callsign} ({flight.type} | {flight.weight_class})</p>
          <p><strong>State:</strong> {flight.state} {flight.is_holding ? "(Hold)" : ""}</p>
          <p><strong>Altitude:</strong> {flight.altitude} ft</p>
          <p><strong>Heading:</strong> {flight.heading}° (Target: {flight.target_heading}°)</p>
          <p><strong>Speed:</strong> {flight.speed} kts (Target: {flight.target_speed} kts)</p>
          <p><strong>Fuel Remaining:</strong> {flight.fuel_level?.toFixed(1)}%</p>
          <p><strong>Emergency Level:</strong> {flight.emergency_index === 0 ? "0 (Normal)" : flight.emergency_index === 1 ? "1 (Low Fuel)" : flight.emergency_index === 3 ? "3 (Critical)" : flight.emergency_index}</p>
          <p><strong>Active STAR:</strong> {flight.active_star || 'None'} (WP: {flight.wp_index})</p>
        </div>
      </div>
    </div>
  );
}

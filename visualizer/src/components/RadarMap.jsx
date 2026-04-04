import React from 'react';
import { MapContainer, TileLayer, Marker, Polyline, Circle, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// SVG icon to represent a plane pointing UP (0 degrees = North)
const createPlaneIcon = (heading, isSelected) => {
  return L.divIcon({
    className: 'custom-plane-icon',
    html: `
      <div style="transform: rotate(${heading}deg); transition: transform 0.3s; display: flex; justify-content: center; align-items: center; width: 24px; height: 24px; background: transparent;">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="${isSelected ? '#007bff' : '#333'}">
          <path d="M12 2 L14 10 L22 14 L22 16 L14 14 L13 20 L15 22 L15 24 L12 23 L9 24 L9 22 L11 20 L10 14 L2 16 L2 14 L10 10 Z"/>
        </svg>
      </div>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12]
  });
};

export default function RadarMap({ flights, selectedFlight, airspace, onSelectFlight }) {
  // Use a generic center
  const center = [40.7, -74.0];

  return (
    <div className="map-panel">
      <MapContainer center={center} zoom={10} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; OpenStreetMap contributors'
        />

        {/* Airspace Nodes & Edges (Optional, but included based on initial prompt) */}
        {airspace.edges.map((edge, idx) => {
          const fromNode = airspace.nodes.find(n => n.id === edge.from);
          const toNode = airspace.nodes.find(n => n.id === edge.to);
          if (fromNode && toNode) {
            return (
              <Polyline key={idx} positions={[fromNode.position, toNode.position]} color="#999" dashArray="5, 10" />
            );
          }
          return null;
        })}
        {airspace.nodes.map(node => (
          <Circle key={node.id} center={node.position} radius={1000} color="red" />
        ))}

        {/* Flights */}
        {flights.map((flight) => {
          const isSelected = selectedFlight && selectedFlight.callsign === flight.callsign;
          return (
            <React.Fragment key={flight.callsign}>
              {/* Plot plane history */}
              {flight.history && (
                <Polyline positions={flight.history} color="gray" weight={2} opacity={0.6} />
              )}
              
              {/* If selected, highlight with a circle marker (fixed pixel size across zoom levels) */}
              {isSelected && (
                <CircleMarker center={[flight.x, flight.y]} radius={15} color="blue" fillOpacity={0.2} pathOptions={{ dashArray: "5, 5" }} />
              )}

              {/* The plane itself */}
              <Marker 
                position={[flight.x, flight.y]} 
                icon={createPlaneIcon(flight.heading, isSelected)}
                eventHandlers={{
                  click: () => onSelectFlight(flight)
                }}
              />
            </React.Fragment>
          );
        })}
      </MapContainer>
    </div>
  );
}

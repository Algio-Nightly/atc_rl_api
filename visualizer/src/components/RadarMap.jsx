import React from 'react';
import { MapContainer, TileLayer, Marker, Polyline, Circle, CircleMarker, Popup, useMapEvents, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import { xyToLatLon, latLonToXY, MAP_CENTER } from '../utils/geo';
import AdminOverlay from './AdminOverlay';
import 'leaflet/dist/leaflet.css';

// SVG icon to represent a plane pointing UP (0 degrees = North)
const createPlaneIcon = (heading, isSelected, scale = 1) => {
  const size = 24 * scale;
  return L.divIcon({
    className: 'custom-plane-icon',
    html: `
      <div style="transform: rotate(${heading}deg); transition: transform 0.3s; display: flex; justify-content: center; align-items: center; width: ${size}px; height: ${size}px; background: transparent;">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${size}" height="${size}" fill="${isSelected ? '#007bff' : '#333'}">
          <path d="M12 2 L14 10 L22 14 L22 16 L14 14 L13 20 L15 22 L15 24 L12 23 L9 24 L9 22 L11 20 L10 14 L2 16 L2 14 L10 10 Z"/>
        </svg>
      </div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2]
  });
};

export default function RadarMap({ 
  flights, 
  selectedFlight, 
  airspace, 
  onSelectFlight, 
  airports = [],
  activeAirport,
  onSelectAirport,
  sendWSMessage
}) {
  const [clickedInfo, setClickedInfo] = React.useState(null);
  const [toastKey, setToastKey] = React.useState(0);
  const [isDraftingAirport, setIsDraftingAirport] = React.useState(false);
  const [isDraftingRunway, setIsDraftingRunway] = React.useState(false);
  const [runwayPoints, setRunwayPoints] = React.useState([]);
  const [mousePos, setMousePos] = React.useState(null);
  const [currentZoom, setCurrentZoom] = React.useState(13);
  const [airportName, setAirportName] = React.useState("");
  const [isRunwayBidirectional, setIsRunwayBidirectional] = React.useState(true);

  React.useEffect(() => {
    if (clickedInfo) {
      const timer = setTimeout(() => setClickedInfo(null), 2000);
      return () => clearTimeout(timer);
    }
  }, [toastKey]);

  // Helper component to capture map events
  function MapClickHandler() {
    const map = useMapEvents({
      click(e) {
        const { lat, lng } = e.latlng;

        if (isDraftingAirport) {
           sendWSMessage('create_airport', { 
             name: airportName || `Airport ${airports.length + 1}`, 
             lat, 
             lon: lng 
           });
           setAirportName("");
           setIsDraftingAirport(false);
           return;
        }

        if (isDraftingRunway) {
           const newPoints = [...runwayPoints, [lat, lng]];
           if (newPoints.length === 2) {
             sendWSMessage('create_runway', { 
               airport_name: activeAirport.name, 
               start: newPoints[0], 
               end: newPoints[1],
               bidirectional: isRunwayBidirectional
             });
             setRunwayPoints([]);
             setIsDraftingRunway(false);
           } else {
             setRunwayPoints(newPoints);
           }
           return;
        }

        const { x, y } = latLonToXY(lat, lng, activeAirport);
        setClickedInfo({ lat, lng, x, y });
        setToastKey(k => k + 1);
      },
      mousemove(e) {
        if (isDraftingRunway && runwayPoints.length === 1) {
          setMousePos([e.latlng.lat, e.latlng.lng]);
        } else {
          if (mousePos) setMousePos(null);
        }
      },
      zoomend() {
        setCurrentZoom(map.getZoom());
      }
    });
    return null;
  }

  // Calculate dynamic sizes based on zoom (base zoom 13)
  const zoomScale = Math.pow(1.2, currentZoom - 13);
  const airportRadius = Math.max(5, 10 * zoomScale);
  const runwayWidth = Math.max(2, 12 * zoomScale);
  const centerLineWidth = Math.max(1, 2 * zoomScale);

  return (
    <div className="map-panel">
      <AdminOverlay 
        airports={airports} 
        activeAirport={activeAirport}
        onSelectAirport={onSelectAirport}
        isDraftingAirport={isDraftingAirport}
        setIsDraftingAirport={setIsDraftingAirport}
        airportName={airportName}
        setAirportName={setAirportName}
        isDraftingRunway={isDraftingRunway}
        setIsDraftingRunway={setIsDraftingRunway}
        isRunwayBidirectional={isRunwayBidirectional}
        setIsRunwayBidirectional={setIsRunwayBidirectional}
      />

      <MapContainer center={[activeAirport.lat, activeAirport.lon]} zoom={13} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; OpenStreetMap contributors'
        />

        {/* Existing Airports */}
        {airports.map(ap => {
          const isActive = activeAirport?.name === ap.name;
          return (
            <React.Fragment key={ap.name}>
              {/* Interaction Point (static screen size) */}
              <CircleMarker
                center={[ap.lat, ap.lon]}
                radius={isActive ? airportRadius * 1.5 : airportRadius}
                color={isActive ? "#007bff" : "#666"}
                fillColor={isActive ? "#fff" : "#999"}
                fillOpacity={1}
                weight={2}
                eventHandlers={{ click: () => onSelectAirport(ap) }}
              >
                <Tooltip permanent direction="top" offset={[0, -10]}>
                  {ap.name}
                </Tooltip>
              </CircleMarker>
            </React.Fragment>
          );
        })}

        {/* Active Airport Runways (Styled as realistic runways) */}
        {activeAirport?.runways?.map((rw, i) => (
          <React.Fragment key={i}>
            {/* The tarmac */}
            <Polyline 
              positions={[[rw.start[0], rw.start[1]], [rw.end[0], rw.end[1]]]} 
              color="#333" 
              weight={runwayWidth} 
              opacity={0.8}
            />
            {/* The white dashed center-line */}
            <Polyline 
              positions={[[rw.start[0], rw.start[1]], [rw.end[0], rw.end[1]]]} 
              color="#fff" 
              weight={centerLineWidth} 
              dashArray={`${centerLineWidth * 5}, ${centerLineWidth * 5}`}
              opacity={0.9}
            />
          </React.Fragment>
        ))}

        {/* Runway Drafting Visualization */}
        {runwayPoints.length === 1 && (
          <>
            <CircleMarker center={runwayPoints[0]} radius={5 * zoomScale} color="red" />
            {mousePos && (
              <Polyline 
                positions={[runwayPoints[0], mousePos]} 
                color="#333" 
                weight={runwayWidth * 0.7} 
                opacity={0.5} 
                dashArray="5, 10" 
              />
            )}
          </>
        )}

        {/* Airspace Nodes & Edges (Optional) */}
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
          const pos = xyToLatLon(flight.x, flight.y, activeAirport);
          const isSelected = selectedFlight && selectedFlight.callsign === flight.callsign;
          const planeScale = Math.max(0.8, 1 * zoomScale);
          return (
            <React.Fragment key={flight.callsign}>
              {/* Plot plane history */}
              {flight.history && (
                <Polyline positions={flight.history.map(h => xyToLatLon(h[0], h[1], activeAirport))} color="gray" weight={2 * zoomScale} opacity={0.6} />
              )}
              
              {/* If selected, highlight with a circle marker */}
              {isSelected && (
                <CircleMarker center={pos} radius={15 * zoomScale} color="blue" fillOpacity={0.2} pathOptions={{ dashArray: "5, 5" }} />
              )}

              {/* The plane itself */}
              <Marker 
                position={pos} 
                icon={createPlaneIcon(flight.heading, isSelected, planeScale)}
                eventHandlers={{
                  click: () => onSelectFlight(flight)
                }}
              />
            </React.Fragment>
          );
        })}

        <MapClickHandler />

        {clickedInfo && (
          <div key={toastKey} className="coordinate-toast">
            <strong>Lat/Lon:</strong> {clickedInfo.lat.toFixed(6)}, {clickedInfo.lng.toFixed(6)}<br/>
            <strong>X/Y:</strong> {clickedInfo.x.toFixed(2)}km, {clickedInfo.y.toFixed(2)}km
          </div>
        )}
      </MapContainer>
    </div>
  );
}

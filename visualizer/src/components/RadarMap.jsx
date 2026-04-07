import React from 'react';
import { MapContainer, TileLayer, Marker, Polyline, Circle, CircleMarker, Popup, useMapEvents, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import { xyToLatLon, latLonToXY, MAP_CENTER } from '../utils/geo';
import 'leaflet/dist/leaflet.css';

const planeIconCache = {};

// SVG icon to represent a plane pointing UP (0 degrees = North)
const createPlaneIcon = (heading, isSelected, scale = 1) => {
  const roundedHeading = Math.round(heading);
  const key = `${roundedHeading}-${isSelected}-${scale}`;
  if (planeIconCache[key]) return planeIconCache[key];

  const size = 24 * scale;
  const icon = L.divIcon({
    className: 'custom-plane-icon',
    html: `
      <div style="transform: rotate(${roundedHeading}deg); transition: transform 0.3s; display: flex; justify-content: center; align-items: center; width: ${size}px; height: ${size}px; background: transparent;">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${size}" height="${size}" fill="${isSelected ? '#007bff' : '#333'}">
          <path d="M12 2 L14 10 L22 14 L22 16 L14 14 L13 20 L15 22 L15 24 L12 23 L9 24 L9 22 L11 20 L10 14 L2 16 L2 14 L10 10 Z"/>
        </svg>
      </div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2]
  });
  
  planeIconCache[key] = icon;
  return icon;
};

const GATE_COLORS = {
  "N": "#4285F4", // Blue
  "NORTH": "#4285F4",
  "S": "#EA4335", // Red
  "SOUTH": "#EA4335",
  "E": "#34A853", // Green
  "EAST": "#34A853",
  "W": "#FBBC05", // Yellow
  "WEST": "#FBBC05"
};

const waypointIconCache = {};

const createWaypointIcon = (label, color, scale = 1, isIAF = false, isFAF = false) => {
  const key = `${label}-${color}-${scale}-${isIAF}-${isFAF}`;
  if (waypointIconCache[key]) return waypointIconCache[key];

  const visualSize = (isIAF || isFAF ? 42 : 36) * scale;
  const hitAreaSize = visualSize * 1.2;
  const borderRadius = isIAF ? '2px' : (isFAF ? '50%' : '50%');
  const transform = isIAF ? 'rotate(45deg)' : 'none';
  const labelTransform = isIAF ? 'rotate(-45deg)' : 'none';

  // Custom styling for FAF
  const fafColor = '#FF8C00'; // DarkOrange
  const finalColor = isFAF ? fafColor : color;
  const border = isFAF ? '3px solid #fff' : '2px solid white';
  const boxShadow = isFAF ? '0 0 15px rgba(255, 140, 0, 0.8)' : '0 4px 10px rgba(0,0,0,0.5)';

  const icon = L.divIcon({
    className: 'custom-waypoint-icon',
    html: `
      <div style="
        width: ${hitAreaSize}px; 
        height: ${hitAreaSize}px; 
        display: flex; 
        justify-content: center; 
        align-items: center; 
        cursor: pointer;
        background: transparent;
        pointer-events: auto; /* Explicitly catch events */
      ">
        <div class="waypoint-visual-marker" style="
          background: ${finalColor}; 
          color: white; 
          border-radius: ${borderRadius}; 
          width: ${visualSize}px; 
          height: ${visualSize}px; 
          display: flex; 
          justify-content: center; 
          align-items: center; 
          font-weight: bold; 
          font-size: ${Math.max(10, (isIAF || isFAF ? 12 : 13) * scale)}px;
          border: ${border};
          box-shadow: ${boxShadow};
          transform: ${transform};
          pointer-events: none;
        ">
          <span style="transform: ${labelTransform}; display: block; pointer-events: none;">
            ${label}
          </span>
        </div>
      </div>
    `,
    iconSize: [hitAreaSize, hitAreaSize],
    iconAnchor: [hitAreaSize / 2, hitAreaSize / 2]
  });

  waypointIconCache[key] = icon;
  return icon;
};

export default function RadarMap({
  flights,
  selectedFlight,
  airspace,
  onSelectFlight,
  airports = [],
  activeAirport,
  activeAirportConfig,
  onSelectAirport,
  sendWSMessage,
  draftingMode,
  setDraftingMode,
  airportName,
  setAirportName,
  runwayPoints,
  setRunwayPoints,
  mousePos,
  setMousePos,
  isRunwayBidirectional,
  starDraft,
  setStarDraft,
  sidDraft,
  setSidDraft,
  activeRunways = [],
  windHeading = 0,
  windSpeed = 0,
  setHoveredWaypoint
}) {
  const [clickedInfo, setClickedInfo] = React.useState(null);
  const [toastKey, setToastKey] = React.useState(0);
  const [currentZoom, setCurrentZoom] = React.useState(13);
  const hoverTimer = React.useRef(null);

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

        if (draftingMode === 'airport') {
          sendWSMessage('create_airport', {
            name: airportName || `Airport ${airports.length + 1}`,
            lat,
            lon: lng
          });
          setAirportName("");
          setDraftingMode(null);
          return;
        }

        if (draftingMode === 'runway') {
          const newPoints = [...runwayPoints, [lat, lng]];
          if (newPoints.length === 2) {
            sendWSMessage('create_runway', {
              airport_code: activeAirport.airport_code,
              start: newPoints[0],
              end: newPoints[1],
              bidirectional: isRunwayBidirectional
            });
            setRunwayPoints([]);
            setDraftingMode(null);
          } else {
            setRunwayPoints(newPoints);
          }
          return;
        }

        if (draftingMode === 'waypoint') {
          const { x, y } = latLonToXY(lat, lng, activeAirport);
          sendWSMessage('create_waypoint', {
            airport_code: activeAirport.airport_code,
            x: x,
            y: y,
            name: `WP_${(activeAirportConfig?.waypoints ? Object.keys(activeAirportConfig.waypoints).length : 0) + 1}`
          });
          return;
        }

        const { x, y } = latLonToXY(lat, lng, activeAirport);
        setClickedInfo({ lat, lng, x, y });
        setToastKey(k => k + 1);
      },
      mousemove(e) {
        if (draftingMode === 'runway' && runwayPoints.length === 1) {
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

      <MapContainer center={[activeAirport.lat, activeAirport.lon]} zoom={11} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; OpenStreetMap contributors'
        />

        {/* Radar Range Rings (10, 20, 30, 45 km) */}
        {[10000, 20000, 30000, 45000].map(r => (
          <Circle
            key={`ring-${r}`}
            center={[activeAirport.lat, activeAirport.lon]}
            radius={r}
            pathOptions={{
              color: r === 45000 ? '#007bff' : '#ccc',
              weight: r === 45000 ? 2 : 1,
              dashArray: '10, 10',
              fillOpacity: r === 45000 ? 0.02 : 0
            }}
          >
            <Tooltip permanent direction="top" opacity={0.5}>
              <span style={{ fontSize: '0.6rem', color: '#999' }}>{r / 1000} KM</span>
            </Tooltip>
          </Circle>
        ))}

        {/* Cardinal Gate Markers (Now at 45km Boundary) */}
        {Object.entries({
          "NORTH": [0, 45],
          "SOUTH": [0, -45],
          "EAST": [45, 0],
          "WEST": [-45, 0]
        }).map(([name, xy]) => {
          const pos = xyToLatLon(xy[0], xy[1], { lat: activeAirport.lat, lon: activeAirport.lon });
          const color = GATE_COLORS[name] || '#888';
          return (
            <CircleMarker
              key={`gate-${name}`}
              center={pos}
              radius={12}
              pathOptions={{
                color: color,
                fillColor: color,
                fillOpacity: 0.8,
                weight: 3,
                dashArray: (draftingMode === 'route' && starDraft.gate === name[0]) ? '5, 5' : null
              }}
            >
              <Tooltip permanent direction="top" offset={[0, -10]}>
                <span style={{ fontWeight: 'bold', color: color, fontSize: '0.8rem' }}>{name} ENTRY</span>
              </Tooltip>
            </CircleMarker>
          );
        })}

        {/* Render Waypoint Pool */}
        {activeAirportConfig && activeAirportConfig.waypoints && (
          Object.values(activeAirportConfig.waypoints).map((wp) => {
            const pos = xyToLatLon(wp.x, wp.y, activeAirport);
            const isIAF = wp.is_iaf || wp.name?.includes("IAF");
            const isFAF = wp.is_faf || wp.name?.includes("FAF");
            const isDP = wp.name?.includes("DP");

            // Color logic: Departure (Greenish), IAF (Purple), FAF (Orange/Gray)
            const color = isIAF ? "#4B0082" : (isDP ? "#28a745" : "#555");
            const label = isIAF ? "IAF" : (isFAF ? "FAF" : (isDP ? "DP" : "WP"));

            return (
              <Marker
                key={`wp-pool-${wp.id}`}
                position={pos}
                icon={createWaypointIcon(label, color, 0.9, isIAF, isFAF)}
                eventHandlers={{
                  click: (e) => {
                    if (draftingMode === 'route') {
                      if (e.originalEvent) e.originalEvent.stopPropagation();
                      setStarDraft(prev => ({ ...prev, sequence: [...prev.sequence, wp.id] }));
                    } else if (draftingMode === 'sid_route') {
                      if (e.originalEvent) e.originalEvent.stopPropagation();
                      setSidDraft(prev => ({ ...prev, sequence: [...prev.sequence, wp.id] }));
                    }
                  },
                  mouseover: () => {
                    if (hoverTimer.current) clearTimeout(hoverTimer.current);
                    hoverTimer.current = setTimeout(() => setHoveredWaypoint(wp), 150);
                  },
                  mouseout: () => {
                    if (hoverTimer.current) clearTimeout(hoverTimer.current);
                    setHoveredWaypoint(null);
                  }
                }}
              >
                <Tooltip direction="top" offset={[0, -10]}>
                  <strong>{wp.name}</strong>
                  {draftingMode === 'route' && <div style={{ color: 'blue' }}>Click to add to route</div>}
                </Tooltip>
              </Marker>
            );
          })
        )}

        {/* Render ACTIVE (Saved) STAR Lines */}
        {activeAirportConfig && activeAirportConfig.stars && (
          Object.entries(activeAirportConfig.stars).map(([gateId, runwayMap]) => {
            const gateColor = GATE_COLORS[gateId.toUpperCase()] || '#888';
            return Object.entries(runwayMap || {}).map(([runwayId, waypointIds]) => {
              // Resolve IDs to Coords
              const positions = (waypointIds || [])
                .map(id => activeAirportConfig.waypoints[id])
                .filter(Boolean)
                .map(wp => xyToLatLon(wp.x, wp.y, activeAirport));

              // Draw the Route Line
              return positions.length > 1 ? (
                <Polyline
                  key={`star-line-${gateId}-${runwayId}`}
                  positions={positions}
                  color={gateColor}
                  weight={2}
                  opacity={0.4}
                  dashArray="5, 10"
                />
              ) : null;
            });
          })
        )}

        {/* Render ACTIVE (Saved) SID Lines */}
        {activeAirportConfig && activeAirportConfig.sids && (
          Object.entries(activeAirportConfig.sids).map(([runwayId, gateMap]) => {
            return Object.entries(gateMap || {}).map(([gateId, waypointIds]) => {
              const gateColor = GATE_COLORS[gateId.toUpperCase()] || '#888';
              const positions = (waypointIds || [])
                .map(id => activeAirportConfig.waypoints[id])
                .filter(Boolean)
                .map(wp => xyToLatLon(wp.x, wp.y, activeAirport));

              return positions.length > 1 ? (
                <Polyline
                  key={`sid-line-${runwayId}-${gateId}`}
                  positions={positions}
                  color={gateColor}
                  weight={2}
                  opacity={0.4}
                  dashArray="5, 10"
                />
              ) : null;
            });
          })
        )}

        {/* Render CURRENT Route Draft Line (Flare!) */}
        {draftingMode === 'route' && starDraft.sequence.length > 0 && (
          <Polyline
            positions={starDraft.sequence
              .map(id => activeAirportConfig.waypoints[id])
              .filter(Boolean)
              .map(wp => xyToLatLon(wp.x, wp.y, activeAirport))
            }
            color={GATE_COLORS[starDraft.gate.toUpperCase()] || '#007bff'}
            weight={4}
            opacity={0.6}
            dashArray="10, 10"
          />
        )}

        {/* Render CURRENT SID Draft Line (Flare!) */}
        {draftingMode === 'sid_route' && sidDraft.sequence.length > 0 && (
          <Polyline
            positions={sidDraft.sequence
              .map(id => activeAirportConfig.waypoints[id])
              .filter(Boolean)
              .map(wp => xyToLatLon(wp.x, wp.y, activeAirport))
            }
            color={GATE_COLORS[sidDraft.gate.toUpperCase()] || '#38a169'}
            weight={4}
            opacity={0.6}
            dashArray="10, 10"
          />
        )}

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
        {activeAirport?.runways?.map((rw, i) => {
          const is_runway_active = activeRunways.includes(rw.id);
          return (
            <React.Fragment key={i}>
              {/* The tarmac */}
              <Polyline
                positions={[[rw.start[0], rw.start[1]], [rw.end[0], rw.end[1]]]}
                color={is_runway_active ? "#111" : "#333"}
                weight={runwayWidth}
                opacity={0.8}
              />
              {/* Active Glow */}
              {is_runway_active && (
                <Polyline
                  positions={[[rw.start[0], rw.start[1]], [rw.end[0], rw.end[1]]]}
                  color="#28a745"
                  weight={runwayWidth + 4}
                  opacity={0.2}
                />
              )}
              {/* The white dashed center-line */}
              <Polyline
                positions={[[rw.start[0], rw.start[1]], [rw.end[0], rw.end[1]]]}
                color={is_runway_active ? "#28a745" : "#fff"}
                weight={centerLineWidth}
                dashArray={`${centerLineWidth * 5}, ${centerLineWidth * 5}`}
                opacity={0.9}
              />
            </React.Fragment>
          );
        })}

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
          const pos = xyToLatLon(flight.x, flight.y, { lat: activeAirport.lat, lon: activeAirport.lon });
          const isSelected = selectedFlight && selectedFlight.callsign === flight.callsign;
          const planeScale = Math.max(0.8, 1 * zoomScale);
          return (
            <React.Fragment key={flight.callsign}>
              {/* Plot plane history */}
              {flight.history && (
                <Polyline positions={flight.history.map(h => xyToLatLon(h[0], h[1], { lat: activeAirport.lat, lon: activeAirport.lon }))} color="gray" weight={2 * zoomScale} opacity={0.6} />
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
            <strong>Lat/Lon:</strong> {clickedInfo.lat.toFixed(6)}, {clickedInfo.lng.toFixed(6)}<br />
            <strong>X/Y:</strong> {clickedInfo.x.toFixed(2)}km, {clickedInfo.y.toFixed(2)}km
          </div>
        )}
      </MapContainer>

      {/* Wind Indicator Overlay */}
      <div className="wind-indicator" style={{
        position: 'absolute',
        top: '20px',
        right: '20px',
        background: 'rgba(0,0,0,0.7)',
        color: '#fff',
        padding: '10px 15px',
        borderRadius: '8px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        zIndex: 1000,
        border: '1px solid #444',
        boxShadow: '0 4px 15px rgba(0,0,0,0.5)',
        pointerEvents: 'none',
        backdropFilter: 'blur(4px)',
        fontFamily: 'monospace'
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
          <span style={{ fontSize: '0.7rem', opacity: 0.7, textTransform: 'uppercase', letterSpacing: '1px' }}>Wind</span>
          <span style={{ fontSize: '1.1rem', fontWeight: 'bold' }}>{Math.round(windHeading)}° / {Math.round(windSpeed)}kts</span>
        </div>
        <div style={{
          width: '32px',
          height: '32px',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          background: '#222',
          borderRadius: '50%',
          border: '2px solid #00ff00',
          transform: `rotate(${(windHeading + 180) % 360}deg)`,
          transition: 'transform 0.5s ease-in-out'
        }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00ff00" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <polyline points="19 12 12 5 5 12"></polyline>
          </svg>
        </div>
      </div>
    </div>
  );
}

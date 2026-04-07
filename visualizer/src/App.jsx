import React, { useState, useEffect, useRef } from 'react';
import { DEFAULT_CENTER } from './utils/geo';
import RadarMap from './components/RadarMap';
import FlightRoster from './components/FlightRoster';
import DevConsole from './components/DevConsole';
import FlightModal from './components/FlightModal';
import AdminPanel from './components/AdminPanel';
import './App.css';

const INITIAL_STATE = {
  simulation_time: 0,
  is_terminal: false,
  active_runways: [],
  wind_heading: 0,
  wind_speed: 0,
  time_scale: 1,
  aircrafts: {},
  events: [],
  airspace: { nodes: [], edges: [] },
  airports: [],
  config: null
};

function App() {
  const [data, setData] = useState(INITIAL_STATE);
  const [logs, setLogs] = useState([]);
  const [selectedFlight, setSelectedFlight] = useState(null);
  const [activeAirport, setActiveAirport] = useState({ ...DEFAULT_CENTER, name: "Loading..." });
  const [hoveredWaypoint, setHoveredWaypoint] = useState(null);
  
  // Drafting States (Unified)
  const [draftingMode, setDraftingMode] = useState(null); // null | 'airport' | 'runway' | 'waypoint' | 'route'
  const [airportName, setAirportName] = useState("");
  const [runwayPoints, setRunwayPoints] = useState([]);
  const [mousePos, setMousePos] = useState(null);
  const [isRunwayBidirectional, setIsRunwayBidirectional] = useState(true);
  
  // STAR Builder specific state
  const [starDraft, setStarDraft] = useState({
    gate: 'N',
    runway_id: null,
    sequence: [] // List of Waypoint IDs
  });
  const wsRef = useRef(null);

  const sendWSMessage = (type, payload) => {
    // 1. Optimistic/Local Update for Development
    if (type === 'create_airport') {
      setData(prev => ({
        ...prev,
        airports: [...(prev.airports || []), { ...payload, name: payload.name || `Airport ${prev.airports.length + 1}`, runways: [] }]
      }));
    }

    if (type === 'create_runway') {
      setData(prev => {
        const airports = (prev.airports || []).map(ap => {
          if (ap.airport_code === payload.airport_code) {
            const rwys = [{ 
              id: payload.runway_id || `RWY_${(ap.runways || []).length + 1}`, 
              heading: payload.heading || 0,
              start: payload.start, 
              end: payload.end 
            }];
            if (payload.bidirectional) {
              const rw_id = payload.runway_id || `RWY_${(ap.runways || []).length + 1}`;
              rwys.push({ 
                id: `${rw_id}_REV`, 
                heading: (payload.heading || 0 + 180) % 360,
                start: payload.end, 
                end: payload.start 
              });
            }
            const updated = { ...ap, runways: [...(ap.runways || []), ...rwys] };
            if (activeAirport?.airport_code === ap.airport_code) {
              setActiveAirport(updated);
            }
            return updated;
          }
          return ap;
        });
        return { ...prev, airports };
      });
    }

    // 2. Network Send
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
    }
  };

  useEffect(() => {
    // 1. Real-time: Connect to WebSocket with Auto-Reconnect
    const connectWS = () => {
      const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => console.log('✅ Connected to RL Backend');

      ws.onmessage = (event) => {
        try {
          const incomingData = JSON.parse(event.data);
          if (incomingData && typeof incomingData === 'object') {
            // 1. Update Simulation State
            setData(prevData => ({ ...prevData, ...incomingData }));
            
            // 2. Accumulate Logs (Independent State)
            if (incomingData.events && incomingData.events.length > 0) {
              setLogs(prevLogs => [...prevLogs, ...incomingData.events].slice(-100));
            }
          }
        } catch (err) {
          console.error("❌ WS Message Error:", err);
        }
      };

      ws.onerror = (error) => console.error('⚠️ WebSocket Error:', error);

      ws.onclose = (e) => {
        console.log(`🔌 Disconnected (Code: ${e.code}). Retrying in 2s...`);
        setTimeout(connectWS, 2000);
      };
    };

    connectWS();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Update active airport when airports list changes
  useEffect(() => {
    if (data.airports && data.airports.length > 0) {
      setActiveAirport(prevActive => {
        if (!prevActive || prevActive.name === "Loading...") {
          return data.airports[0];
        }
        return data.airports.find(a => a.name === prevActive.name) || data.airports[0];
      });
    }
  }, [data.airports]);

  const handleFlightSelect = (flight) => setSelectedFlight(flight);

  const handleSendCommand = (cmd) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'command', payload: cmd }));
    }
  };

  const handleCloseModal = () => setSelectedFlight(null);

  const flightsList = data.aircrafts ? Object.values(data.aircrafts) : [];

  return (
    <div className="dashboard-container">
      <AdminPanel
        airports={data.airports || []}
        activeAirport={activeAirport}
        activeAirportConfig={data.config}
        onSelectAirport={(ap) => {
          setActiveAirport(ap);
          sendWSMessage('select_airport', { code: ap.airport_code });
        }}
        sendWSMessage={sendWSMessage}
        
        draftingMode={draftingMode}
        setDraftingMode={setDraftingMode}

        airportName={airportName}
        setAirportName={setAirportName}
        isRunwayBidirectional={isRunwayBidirectional}
        setIsRunwayBidirectional={setIsRunwayBidirectional}

        starDraft={starDraft}
        setStarDraft={setStarDraft}
      />

      <RadarMap
        flights={flightsList}
        selectedFlight={selectedFlight}
        onSelectFlight={handleFlightSelect}
        airspace={data.airspace || { nodes: [], edges: [] }}
        airports={data.airports || []}
        activeAirport={activeAirport}
        setActiveAirport={setActiveAirport}
        activeAirportConfig={data.config}
        activeRunways={data.active_runways || []}
        windHeading={data.wind_heading || 0}
        windSpeed={data.wind_speed || 0}
        onSelectAirport={(ap) => {
          setActiveAirport(ap);
          sendWSMessage('select_airport', { code: ap.airport_code });
        }}
        sendWSMessage={sendWSMessage}
        
        draftingMode={draftingMode}
        setDraftingMode={setDraftingMode}
        
        airportName={airportName}
        setAirportName={setAirportName}
        runwayPoints={runwayPoints}
        setRunwayPoints={setRunwayPoints}
        mousePos={mousePos}
        setMousePos={setMousePos}
        isRunwayBidirectional={isRunwayBidirectional}
        
        starDraft={starDraft}
        setStarDraft={setStarDraft}
        setHoveredWaypoint={setHoveredWaypoint}
      />

      <FlightRoster
        gameState={data}
        flights={flightsList}
        onSelectFlight={handleFlightSelect}
        sendWSMessage={sendWSMessage}
        hoveredWaypoint={hoveredWaypoint}
      />

      <DevConsole actions={logs} onSendCommand={handleSendCommand} />

      {/* Renders over everything when a flight is selected */}
      <FlightModal
        flight={selectedFlight}
        onClose={handleCloseModal}
      />
    </div>
  );
}

export default App;

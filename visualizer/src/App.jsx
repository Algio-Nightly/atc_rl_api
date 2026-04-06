import React, { useState, useEffect, useRef } from 'react';
import { DEFAULT_CENTER } from './utils/geo';
import RadarMap from './components/RadarMap';
import FlightRoster from './components/FlightRoster';
import DevConsole from './components/DevConsole';
import FlightModal from './components/FlightModal';
import './App.css';

const INITIAL_STATE = {
  simulation_time: 0,
  is_terminal: false,
  active_runway: null,
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
  const [selectedFlight, setSelectedFlight] = useState(null);
  const [activeAirport, setActiveAirport] = useState({ ...DEFAULT_CENTER, name: "Loading..." });
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
          if (ap.name === payload.airport_name) {
            const rwys = [{ start: payload.start, end: payload.end }];
            if (payload.bidirectional) {
              rwys.push({ start: payload.end, end: payload.start });
            }
            const updated = { ...ap, runways: [...(ap.runways || []), ...rwys] };
            if (activeAirport?.name === ap.name) {
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
    // 1. Bootstrap: Fetch current state from REST API
    const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const fetchState = () => {
      fetch(`${apiBase}/state`)
        .then(res => res.json())
        .then(initialData => {
          setData(initialData);
          if (initialData.airports && initialData.config) {
            const current = initialData.airports.find(a => a.name === initialData.config.name);
            if (current) setActiveAirport(current);
          }
        })
        .catch(err => console.error("Initial fetch failed:", err));
    };
    fetchState();

    // 2. Real-time: Connect to WebSocket with Auto-Reconnect
    const connectWS = () => {
      const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => console.log('✅ Connected to RL Backend');

      ws.onmessage = (event) => {
        try {
          const incomingData = JSON.parse(event.data);
          if (incomingData && typeof incomingData === 'object') {
            setData(prevData => {
              const newData = { ...prevData, ...incomingData };
              if (newData.airports) {
                setActiveAirport(prevActive => {
                  if (!prevActive || prevActive.name === "Loading...") {
                    return newData.airports[0] || prevActive;
                  }
                  return newData.airports.find(a => a.name === prevActive.name) || prevActive;
                });
              }
              return newData;
            });
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
      <RadarMap
        flights={flightsList}
        selectedFlight={selectedFlight}
        onSelectFlight={handleFlightSelect}
        airspace={data.airspace || { nodes: [], edges: [] }}
        airports={data.airports || []}
        activeAirport={activeAirport}
        activeAirportConfig={data.config}
        onSelectAirport={setActiveAirport}
        sendWSMessage={sendWSMessage}
      />

      <FlightRoster
        gameState={data}
        flights={flightsList}
        onSelectFlight={handleFlightSelect}
        sendWSMessage={sendWSMessage}
      />

      <DevConsole actions={data.events || []} onSendCommand={handleSendCommand} />

      {/* Renders over everything when a flight is selected */}
      <FlightModal
        flight={selectedFlight}
        onClose={handleCloseModal}
      />
    </div>
  );
}

export default App;

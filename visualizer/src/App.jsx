import React, { useState, useEffect, useRef } from 'react';
import { mockData } from './mockData';
import { DEFAULT_CENTER } from './utils/geo';
import RadarMap from './components/RadarMap';
import FlightRoster from './components/FlightRoster';
import DevConsole from './components/DevConsole';
import FlightModal from './components/FlightModal';
import './App.css'; // Just in case, though we put styles in index.css

function App() {
  const [data, setData] = useState(mockData);
  const [selectedFlight, setSelectedFlight] = useState(null);
  const [activeAirport, setActiveAirport] = useState(mockData.airports[0] || { ...DEFAULT_CENTER, name: "Default" });
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
            // Ensure local selection is updated too
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
    // Determine WS URL (fallback to localhost:8080)
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8080/ws';
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('Connected to RL Backend WebSocket');
    };

    ws.onmessage = (event) => {
      try {
        const incomingData = JSON.parse(event.data);
        if (incomingData && typeof incomingData === 'object') {
           setData(prevData => {
             const newData = { ...prevData, ...incomingData };
             // Keep active airport object in sync if its data changed in the backend
             setActiveAirport(prevActive => {
               if (!prevActive || !newData.airports) return prevActive;
               const updated = newData.airports.find(a => a.name === prevActive.name);
               return updated || prevActive;
             });
             return newData;
           });
        }
      } catch (err) {
        console.error("Error parsing WS message:", err);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket Error:', error);
    };

    ws.onclose = () => {
      console.log('Disconnected from RL Backend');
    };

    return () => {
      ws.close();
    };
  }, []);

  const handleFlightSelect = (flight) => {
    setSelectedFlight(flight);
  };

  const handleSendCommand = (cmd) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'command', payload: cmd }));
    } else {
      console.warn("Cannot send command, WebSocket is not open.");
    }
  };

  const handleCloseModal = () => {
    setSelectedFlight(null);
  };

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
        onSelectAirport={setActiveAirport}
        sendWSMessage={sendWSMessage}
      />
      
      <FlightRoster 
        gameState={data}
        flights={flightsList} 
        onSelectFlight={handleFlightSelect}
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

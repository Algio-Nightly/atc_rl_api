import React, { useState, useEffect, useRef } from 'react';
import { mockData } from './mockData';
import RadarMap from './components/RadarMap';
import FlightRoster from './components/FlightRoster';
import DevConsole from './components/DevConsole';
import FlightModal from './components/FlightModal';
import './App.css'; // Just in case, though we put styles in index.css

function App() {
  const [data, setData] = useState(mockData);
  const [selectedFlight, setSelectedFlight] = useState(null);
  const wsRef = useRef(null);

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
        // We assume the payload contains the full state reflecting our desired schema
        if (incomingData && typeof incomingData === 'object') {
           setData(prevData => ({ ...prevData, ...incomingData }));
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

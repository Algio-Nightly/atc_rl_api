export const mockData = {
  simulation_time: 124.5,
  is_terminal: false,
  active_runway: "27R",
  wind_heading: 260.0,
  wind_speed: 12.5,
  time_scale: 1.0,
  aircrafts: {
    "UA123": {
      callsign: "UA123",
      type: "B738",
      weight_class: "Medium",
      x: 40.7128,
      y: -74.0060,
      altitude: 12000,
      heading: 85.0,
      target_heading: 90.0,
      speed: 280,
      target_speed: 250,
      state: "ENROUTE",
      fuel_level: 45.0,
      emergency_index: 0,
      active_star: "STAR_ALPHA",
      wp_index: 2,
      is_holding: false
    },
    "DL456": {
      callsign: "DL456",
      type: "A320",
      weight_class: "Medium",
      x: 40.6500,
      y: -73.9000,
      altitude: 5000,
      heading: 120.0,
      target_heading: 120.0,
      speed: 210,
      target_speed: 210,
      state: "HOLDING",
      fuel_level: 18.0,
      emergency_index: 1,
      active_star: null,
      wp_index: 1,
      is_holding: true
    }
  },
  events: [
    { type: "RL_ACTION", msg: "[Step 44 | Reward: +05.0] Hold DL456 at WPT_BRAVO" },
    { type: "RL_ACTION", msg: "[Step 45 | Reward: -15.4] Route UA123 to WPT_ALPHA" }
  ],
  airspace: {
    nodes: [
      { id: "WPT_ALPHA", position: [40.7500, -74.1000] },
      { id: "WPT_BRAVO", position: [40.6000, -73.8000] }
    ],
    edges: [
      { from: "WPT_ALPHA", to: "WPT_BRAVO" }
    ]
  }
};

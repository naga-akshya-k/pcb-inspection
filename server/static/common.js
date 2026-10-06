/* ==========================================================================
   SHARED INDUSTRIAL STATION CONTROLLER, NAVIGATION & GLOBAL BOARD SYNC
   ========================================================================== */

// Auto-highlight active multi-page navigation button based on current URL path
document.addEventListener('DOMContentLoaded', () => {
  const path = window.location.pathname;
  const navLinks = document.querySelectorAll('.ind-nav-menu a.nav-tab-btn');

  navLinks.forEach(link => {
    const href = link.getAttribute('href');
    if (href === path || (path === '/' && href === '/') || (path === '' && href === '/')) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });

  // Global Server Health Polling
  checkGlobalServerHealth();
  setInterval(checkGlobalServerHealth, 10000);
});

async function checkGlobalServerHealth() {
  const telemServer = document.getElementById('telemServer');
  if (!telemServer) return;
  try {
    const resp = await fetch('/health');
    if (resp.ok) {
      const data = await resp.json();
      telemServer.textContent = `SMT LINE 01 ONLINE • ${data.depth_engine_type || '3D Leveled'}`;
      telemServer.className = 'telem-val text-pass';
    }
  } catch (e) {
    telemServer.textContent = 'LINE OFFLINE (Reconnecting...)';
    telemServer.className = 'telem-val text-fail';
  }
}

/* ==========================================================================
   GLOBAL AOI BOARD SYNCHRONIZATION SYSTEM
   Synchronizes the active inspected board simultaneously across all views:
   Live Inspection, 360 3D Twin, 3D Photometrics, 3D X-Ray, Metrology, etc.
   ========================================================================== */

const AOI_SYNC_CHANNEL_NAME = 'aoi_board_sync_channel';
let aoiSyncBroadcast = null;
try {
  aoiSyncBroadcast = new BroadcastChannel(AOI_SYNC_CHANNEL_NAME);
} catch (e) {
  console.warn("BroadcastChannel not supported", e);
}

// Function to broadcast active board change to all pages
function setGlobalActiveBoard(boardInfo) {
  if (!boardInfo) return;
  
  try {
    localStorage.setItem('aoi_active_board', JSON.stringify(boardInfo));
    localStorage.setItem('activeBoard3D', JSON.stringify({
      serial: boardInfo.serial || boardInfo.board_id,
      verdict: boardInfo.verdict || 'PASS',
      components: boardInfo.components || [],
      metrology: boardInfo.metrology || [],
      image_b64: boardInfo.image_b64 || boardInfo.overlay_b64
    }));
  } catch (err) {
    console.warn("localStorage write error", err);
  }

  if (aoiSyncBroadcast) {
    try {
      aoiSyncBroadcast.postMessage({ type: 'AOI_BOARD_CHANGED', data: boardInfo });
    } catch (err) {
      console.warn("BroadcastChannel post error", err);
    }
  }

  window.dispatchEvent(new CustomEvent('aoi_board_changed', { detail: boardInfo }));

  // Also push to backend if available
  fetch('/api/active-board', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(boardInfo)
  }).catch(() => {});
}

// Function for any page to get the current active board
async function getGlobalActiveBoard() {
  // Try localStorage first
  try {
    const local = localStorage.getItem('aoi_active_board');
    if (local) {
      const parsed = JSON.parse(local);
      if (parsed && (parsed.board_id || parsed.serial) && parsed.verdict && parsed.verdict !== 'READY') {
        return parsed;
      }
    }
  } catch (e) {}

  // Fallback to backend API
  try {
    const res = await fetch('/api/active-board');
    if (res.ok) {
      const data = await res.json();
      return data;
    }
  } catch (e) {}

  return null;
}

// Function for any page to subscribe to live board changes
function onGlobalActiveBoardChange(callback) {
  if (typeof callback !== 'function') return;

  if (aoiSyncBroadcast) {
    aoiSyncBroadcast.addEventListener('message', (event) => {
      if (event.data && event.data.type === 'AOI_BOARD_CHANGED') {
        callback(event.data.data);
      }
    });
  }

  window.addEventListener('storage', (event) => {
    if (event.key === 'aoi_active_board' && event.newValue) {
      try {
        callback(JSON.parse(event.newValue));
      } catch (e) {}
    }
  });

  window.addEventListener('aoi_board_changed', (event) => {
    if (event.detail) callback(event.detail);
  });
}

/* ==========================================================================
   INSPECTRA REAL-TIME SERVER-SENT EVENTS (SSE) & SESSION CLIENT
   Dynamically synchronizes all open browser tabs simultaneously in real time.
   ========================================================================== */

const INSPECTRA_BUS_CHANNEL = 'inspectra_global_bus';
let inspectraBroadcast = null;
try {
  inspectraBroadcast = new BroadcastChannel(INSPECTRA_BUS_CHANNEL);
} catch (e) {
  console.warn("BroadcastChannel not supported", e);
}

// Global SSE connection
let inspectraEventSource = null;
function initInspectraSSE() {
  if (inspectraEventSource) return;
  try {
    inspectraEventSource = new EventSource('/api/events');

    function handleRemoteEvent(evt) {
      try {
        const sessionData = JSON.parse(evt.data);
        if (sessionData && (sessionData.pcb_id || sessionData.serial_number)) {
          // Sync with local active board state
          setGlobalActiveBoard({
            board_id: sessionData.serial_number,
            serial: sessionData.serial_number,
            pcb_id: sessionData.pcb_id,
            verdict: sessionData.final_verdict || sessionData.ai_verdict,
            defective_components: sessionData.defective_components,
            image_url: sessionData.image_url,
            overlay_b64: sessionData.overlay_image_b64,
            depth_heatmap_b64: sessionData.depth_heatmap_b64,
            components: sessionData.components,
            metrology: sessionData.metrology,
            defects: sessionData.defects,
            session: sessionData
          });

          // Dispatch session specific event
          if (inspectraBroadcast) {
            inspectraBroadcast.postMessage({ type: 'INSPECTRA_SESSION_SYNC', session: sessionData });
          }
          window.dispatchEvent(new CustomEvent('inspectra_session_changed', { detail: sessionData }));
        }
      } catch (err) {
        console.warn("Error parsing SSE event data", err);
      }
    }

    inspectraEventSource.addEventListener('initial_state', handleRemoteEvent);
    inspectraEventSource.addEventListener('inspection_completed', handleRemoteEvent);
    inspectraEventSource.addEventListener('board_selected', handleRemoteEvent);
    inspectraEventSource.addEventListener('human_review_updated', handleRemoteEvent);

    inspectraEventSource.onerror = () => {
      // Reconnection handled automatically by browser EventSource
    };
  } catch (err) {
    console.warn("Failed to initialize SSE EventSource", err);
  }
}

// Initialize SSE on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initInspectraSSE);
} else {
  initInspectraSSE();
}

// Function to fetch active inspection session
async function getInspectraActiveSession() {
  try {
    const res = await fetch('/api/session/active');
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn("getInspectraActiveSession error", err);
  }
  return null;
}

// Function to fetch specific session by pcb_id or serial
async function getInspectraSession(pcbId) {
  try {
    const res = await fetch(`/api/session/${encodeURIComponent(pcbId)}`);
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn("getInspectraSession error", err);
  }
  return null;
}

// Function to select active board and notify all tabs
async function selectInspectraBoard(pcbId) {
  try {
    const res = await fetch(`/api/session/select/${encodeURIComponent(pcbId)}`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      return data.active_session;
    }
  } catch (err) {
    console.warn("selectInspectraBoard error", err);
  }
  return null;
}

// Function to submit operator human review / override
async function submitInspectraHumanReview(payload) {
  try {
    const res = await fetch('/api/session/human-review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      const data = await res.json();
      return data.session;
    }
  } catch (err) {
    console.warn("submitInspectraHumanReview error", err);
  }
  return null;
}

// Function to subscribe to dynamic session changes across tabs
function onInspectraSessionChange(callback) {
  if (typeof callback !== 'function') return;

  if (inspectraBroadcast) {
    inspectraBroadcast.addEventListener('message', (event) => {
      if (event.data && event.data.type === 'INSPECTRA_SESSION_SYNC') {
        callback(event.data.session);
      }
    });
  }

  window.addEventListener('inspectra_session_changed', (event) => {
    if (event.detail) callback(event.detail);
  });
}

// Helper to check URL query parameters for pcb_id
function getUrlPcbId() {
  const params = new URLSearchParams(window.location.search);
  return params.get('pcb_id') || params.get('board_id') || params.get('serial');
}


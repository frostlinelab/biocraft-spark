import { useState, useEffect } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import heroImg from './assets/hero.png'
import './App.css'

interface PingResult {
  status: 'idle' | 'loading' | 'success' | 'error';
  data?: any;
  error?: string;
}

function App() {
  const [count, setCount] = useState(0)
  const [dockerStatus, setDockerStatus] = useState<PingResult>({ status: 'idle' })
  const [executorStatus, setExecutorStatus] = useState<PingResult>({ status: 'idle' })
  const [schedulerStatus, setSchedulerStatus] = useState<PingResult>({ status: 'idle' })
  const [pluginStatus, setPluginStatus] = useState<PingResult>({ status: 'idle' })

  const API_BASE = 'http://127.0.0.1:8000';

  const checkDocker = async () => {
    setDockerStatus({ status: 'loading' })
    try {
      const res = await fetch(`${API_BASE}/debug/ping-docker`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();
      setDockerStatus({ status: 'success', data })
    } catch (e: any) {
      setDockerStatus({ status: 'error', error: e.message || 'Generic error' })
    }
  }

  const checkExecutor = async () => {
    setExecutorStatus({ status: 'loading' })
    try {
      const res = await fetch(`${API_BASE}/debug/ping-executor`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();
      setExecutorStatus({ status: 'success', data })
    } catch (e: any) {
      setExecutorStatus({ status: 'error', error: e.message || 'Generic error' })
    }
  }

  const checkScheduler = async () => {
    setSchedulerStatus({ status: 'loading' })
    try {
      const res = await fetch(`${API_BASE}/debug/ping-scheduler`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();
      setSchedulerStatus({ status: 'success', data })
    } catch (e: any) {
      setSchedulerStatus({ status: 'error', error: e.message || 'Generic error' })
    }
  }

  const checkPlugin = async () => {
    setPluginStatus({ status: 'loading' })
    try {
      const res = await fetch(`${API_BASE}/debug/ping-plugin`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();
      setPluginStatus({ status: 'success', data })
    } catch (e: any) {
      setPluginStatus({ status: 'error', error: e.message || 'Generic error' })
    }
  }

  useEffect(() => {
    checkPlugin();
  }, [])

  return (
    <>
      <section id="center">
        <div className="hero">
          <img src={heroImg} className="base" width="170" height="179" alt="" />
          <img src={reactLogo} className="framework" alt="React logo" />
          <img src={viteLogo} className="vite" alt="Vite logo" />
        </div>
        <div>
          <h1>Biocraft Spark</h1>
          <p>
            Desktop GUI for design, scheduling and execution of bioinformatics DAG workflows.
          </p>
        </div>
        <button
          type="button"
          className="counter"
          onClick={() => setCount((count) => count + 1)}
        >
          Click count: {count}
        </button>
      </section>

      <div className="ticks"></div>

      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', padding: '1.5rem', textAlign: 'left' }}>
        <div style={{ padding: '1rem', border: '1px solid #ccc', borderRadius: '8px' }}>
          <h3>Docker Sidecar</h3>
          <button onClick={checkDocker} disabled={dockerStatus.status === 'loading'}>
            {dockerStatus.status === 'loading' ? 'Checking...' : 'Ping Docker'}
          </button>
          {dockerStatus.status === 'success' && (
            <p style={{ color: 'green' }}>Online! Containers found: {dockerStatus.data?.containers?.length || 0}</p>
          )}
          {dockerStatus.status === 'error' && (
            <p style={{ color: 'red' }}>Error: {dockerStatus.error}</p>
          )}
        </div>

        <div style={{ padding: '1rem', border: '1px solid #ccc', borderRadius: '8px' }}>
          <h3>Container Executor</h3>
          <button onClick={checkExecutor} disabled={executorStatus.status === 'loading'}>
            {executorStatus.status === 'loading' ? 'Running Py pod...' : 'Run Executor'}
          </button>
          {executorStatus.status === 'success' && (
            <div>
              <p style={{ color: 'green' }}>Status: {executorStatus.data?.status}</p>
              <pre style={{ fontSize: '0.8rem', background: '#333', padding: '4px' }}>{executorStatus.data?.stdout?.trim()}</pre>
            </div>
          )}
          {executorStatus.status === 'error' && (
            <p style={{ color: 'red' }}>Error: {executorStatus.error}</p>
          )}
        </div>

        <div style={{ padding: '1rem', border: '1px solid #ccc', borderRadius: '8px' }}>
          <h3>DAG Scheduler</h3>
          <button onClick={checkScheduler} disabled={schedulerStatus.status === 'loading'}>
            {schedulerStatus.status === 'loading' ? 'Running DAG...' : 'Test Scheduler'}
          </button>
          {schedulerStatus.status === 'success' && (
            <p style={{ color: 'green' }}>DAG Run Successful! {schedulerStatus.data?.status}</p>
          )}
          {schedulerStatus.status === 'error' && (
            <p style={{ color: 'red' }}>Error: {schedulerStatus.error}</p>
          )}
        </div>

        <div style={{ padding: '1rem', border: '1px solid #ccc', borderRadius: '8px' }}>
          <h3>Plugin loading</h3>
          <p>Initial validation on mounts:</p>
          {pluginStatus.status === 'loading' && <p>Loading...</p>}
          {pluginStatus.status === 'success' && (
            <p style={{ color: 'green' }}>Loaded Spec: {pluginStatus.data?.plugin} v{pluginStatus.data?.version}</p>
          )}
          {pluginStatus.status === 'error' && (
            <p style={{ color: 'red' }}>Error: {pluginStatus.error}</p>
          )}
        </div>
      </section>

      <div className="ticks"></div>
      <section id="spacer"></section>
    </>
  )
}

export default App

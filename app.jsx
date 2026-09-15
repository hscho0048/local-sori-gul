const App = () => {
  const [status, setStatus] = React.useState('연결 중…');
  React.useEffect(() => { window.SoriBridge.job().then((job) => setStatus(`bridge ok · job ${job.state}`), (error) => setStatus(String(error))); }, []);
  return <main style={{ padding: 24 }}>소리글 · {status}</main>;
};
ReactDOM.createRoot(document.getElementById('root')).render(<App />);

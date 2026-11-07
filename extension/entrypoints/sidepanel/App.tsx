// Explicit extension: on case-insensitive filesystems './HealthStatus' resolves to healthStatus.ts.
import HealthStatus from './HealthStatus.tsx';
import CaptureButton from './CaptureButton';
import CaptureResult from './CaptureResult';
import { useCaptureState } from './useCaptureState';

export default function App() {
  const state = useCaptureState();

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', padding: '1rem' }}>
      <h1>Screen to Cart</h1>
      <HealthStatus />
      <CaptureButton state={state} />
      {state?.status === 'cached' && <p>This moment was already identified.</p>}
      {state?.status === 'captured' && <CaptureResult capture={state.capture} />}
    </main>
  );
}

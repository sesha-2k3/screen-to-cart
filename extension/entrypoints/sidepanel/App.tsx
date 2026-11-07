// Explicit extension: on case-insensitive filesystems './HealthStatus' resolves to healthStatus.ts.
import HealthStatus from './HealthStatus.tsx';
import CaptureButton from './CaptureButton';

export default function App() {
  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', padding: '1rem' }}>
      <h1>Screen to Cart</h1>
      <HealthStatus />
      <CaptureButton />
    </main>
  );
}

import type { components } from '@/lib/api-types';

type ProductCandidate = components['schemas']['ProductCandidate'];

export default function CandidateList({ candidates }: { candidates: ProductCandidate[] }) {
  const [top, ...others] = candidates;
  if (!top) return <p>No product found in this frame.</p>;
  return (
    <section>
      <h2 style={{ fontSize: '1.2rem', marginBottom: 4 }}>
        {top.brand} {top.model}
      </h2>
      <p style={{ marginTop: 0 }}>
        {top.category} · {Math.round(top.confidence * 100)}% sure
      </p>
      {others.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {/* Phase 3 searches a chip's product when it's clicked. */}
          {others.map((candidate) => (
            <span
              key={`${candidate.brand} ${candidate.model}`}
              style={{ border: '1px solid #ccc', borderRadius: 12, padding: '2px 10px' }}
            >
              {candidate.brand} {candidate.model}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

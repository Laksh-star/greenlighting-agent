import type { Comparable } from "../types";

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0
});

export function ComparableCard({
  movie,
  onToggle
}: {
  movie: Comparable;
  onToggle?: () => void;
}) {
  return (
    <article className={`movie-card ${movie.selected ? "selected" : ""}`}>
      <h3>{movie.title}</h3>
      <div className="movie-meta">
        <span>{movie.year}</span>
        <span>{movie.rating.toFixed(1)} rating</span>
        <span>{currency.format(movie.budget)} budget</span>
      </div>
      <p>{movie.fit}</p>
      <p><strong>Revenue signal:</strong> {currency.format(movie.revenue)}</p>
      {onToggle ? (
        <button className="secondary-action" onClick={onToggle}>
          {movie.selected ? "Remove" : "Add"}
        </button>
      ) : null}
    </article>
  );
}

export function RecommendationCard({
  recommendation,
  confidence,
  riskScore,
  drivers
}: {
  recommendation: string;
  confidence: string;
  riskScore: string;
  drivers: string[];
}) {
  return (
    <article className="recommendation-card">
      <span className="recommendation">{recommendation}</span>
      <div className="brief-grid compact-grid">
        <div className="metric-block"><span>Confidence</span><strong>{confidence}</strong></div>
        <div className="metric-block"><span>Risk</span><strong>{riskScore}</strong></div>
      </div>
      <ul className="driver-list">
        {drivers.map((driver) => <li key={driver}>{driver}</li>)}
      </ul>
    </article>
  );
}

export function PackageGateCard({
  locked,
  ready
}: {
  locked: boolean;
  ready: boolean;
}) {
  return (
    <article className="recommendation-card">
      <span className="package-state">{locked ? "Locked for export" : "Needs approval"}</span>
      <p>
        {ready
          ? "Comparables, assumptions, and final recommendation are approved."
          : "The package cannot be locked until the approval checks are complete."}
      </p>
    </article>
  );
}

import { Link } from "react-router";

export function NotFound() {
  return (
    <section className="max-w-prose">
      <h1 className="text-2xl font-bold">There's no page here</h1>
      <p className="mt-2">
        <Link to="/" className="text-guard underline">
          Go to the list of attacks
        </Link>
      </p>
    </section>
  );
}

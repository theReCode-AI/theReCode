export function LoadingState({ message = "Loading..." }: { message?: string }) {
  return <p className="state-message">{message}</p>;
}

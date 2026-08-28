export function ErrorState({ message }: { message: string }) {
  return <p className="state-message state-error">{message}</p>;
}

import { Alert } from "flowbite-react";

export function EmptyState({ message }: { message: string }) {
  return (
    <Alert color="info" className="state-message">
      {message}
    </Alert>
  );
}

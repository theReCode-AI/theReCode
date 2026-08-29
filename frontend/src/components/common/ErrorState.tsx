import { Alert } from "flowbite-react";

export function ErrorState({ message }: { message: string }) {
  return (
    <Alert color="failure" className="state-error">
      {message}
    </Alert>
  );
}

import { Spinner } from "flowbite-react";

export function LoadingState({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400" role="status">
      <Spinner size="sm" />
      <span className="state-message">{message}</span>
    </div>
  );
}

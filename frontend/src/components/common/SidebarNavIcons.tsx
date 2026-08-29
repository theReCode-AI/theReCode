import type { ComponentProps, FC } from "react";

type IconProps = ComponentProps<"svg">;

export const DashboardIcon: FC<IconProps> = (props) => (
  <svg
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
    fill="currentColor"
    viewBox="0 0 24 24"
    {...props}
  >
    <path d="M10 3H3v7h7V3Zm11 0h-7v7h7V3ZM10 14H3v7h7v-7Zm11 0h-7v7h7v-7Z" />
  </svg>
);

export const ProjectsIcon: FC<IconProps> = (props) => (
  <svg
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
    fill="currentColor"
    viewBox="0 0 24 24"
    {...props}
  >
    <path d="M4 5a2 2 0 0 1 2-2h4.586a1 1 0 0 1 .707.293l2.414 2.414A1 1 0 0 0 14.414 6H20a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5Z" />
  </svg>
);

export const SettingsIcon: FC<IconProps> = (props) => (
  <svg
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
    fill="currentColor"
    viewBox="0 0 24 24"
    {...props}
  >
    <path
      fillRule="evenodd"
      d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM9.6 2.7a1 1 0 0 1 .8-.7h3.2a1 1 0 0 1 .8.7l.3 1.2a6.9 6.9 0 0 1 1.6.9l1.1-.5a1 1 0 0 1 1.2.4l1.6 2.8a1 1 0 0 1-.2 1.3l-.9.9a7 7 0 0 1 0 1.8l.9.9a1 1 0 0 1 .2 1.3l-1.6 2.8a1 1 0 0 1-1.2.4l-1.1-.5a6.9 6.9 0 0 1-1.6.9l-.3 1.2a1 1 0 0 1-.8.7h-3.2a1 1 0 0 1-.8-.7l-.3-1.2a6.9 6.9 0 0 1-1.6-.9l-1.1.5a1 1 0 0 1-1.2-.4l-1.6-2.8a1 1 0 0 1 .2-1.3l.9-.9a7 7 0 0 1 0-1.8l-.9-.9a1 1 0 0 1-.2-1.3l1.6-2.8a1 1 0 0 1 1.2-.4l1.1.5a6.9 6.9 0 0 1 1.6-.9l.3-1.2Z"
      clipRule="evenodd"
    />
  </svg>
);

/** Folder / projects metric */
export const ProjectsStatIcon: FC<IconProps> = (props) => (
  <svg
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    strokeWidth={1.75}
    stroke="currentColor"
    {...props}
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M3.75 6.75A2.25 2.25 0 0 1 6 4.5h3.879a1.5 1.5 0 0 1 1.06.44l1.122 1.12a1.5 1.5 0 0 0 1.06.44H18a2.25 2.25 0 0 1 2.25 2.25v9a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18V6.75Z"
    />
  </svg>
);

/** Play / active runs metric */
export const ActiveRunsStatIcon: FC<IconProps> = (props) => (
  <svg
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    strokeWidth={1.75}
    stroke="currentColor"
    {...props}
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z"
    />
  </svg>
);

/** Clock / recent runs metric */
export const RecentRunsStatIcon: FC<IconProps> = (props) => (
  <svg
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    strokeWidth={1.75}
    stroke="currentColor"
    {...props}
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
    />
  </svg>
);

/** Plus — create project */
export const PlusIcon: FC<IconProps> = (props) => (
  <svg
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    strokeWidth={1.75}
    stroke="currentColor"
    {...props}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
  </svg>
);

/** Chevron — open project */
export const ChevronRightIcon: FC<IconProps> = (props) => (
  <svg
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    strokeWidth={1.75}
    stroke="currentColor"
    {...props}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
  </svg>
);

/** Chat / conversation */
export const ChatIcon: FC<IconProps> = (props) => (
  <svg
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    strokeWidth={1.75}
    stroke="currentColor"
    {...props}
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M8.625 9.75h6.75M8.625 13.5h4.125M20.25 12a8.25 8.25 0 1 1-3.05-6.372L21 3.75l-.878 4.078A8.22 8.22 0 0 1 20.25 12Z"
    />
  </svg>
);

/** Git / repositories */
export const RepositoriesStatIcon: FC<IconProps> = (props) => (
  <svg
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    strokeWidth={1.75}
    stroke="currentColor"
    {...props}
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M17.25 6.75a4.5 4.5 0 0 1-4.5 4.5H9.75v3.75m7.5-8.25a4.5 4.5 0 0 0-4.5-4.5H6.75A2.25 2.25 0 0 0 4.5 4.5v15A2.25 2.25 0 0 0 6.75 21.75h10.5A2.25 2.25 0 0 0 19.5 19.5V11.25a4.5 4.5 0 0 0-2.25-4.5Z"
    />
  </svg>
);

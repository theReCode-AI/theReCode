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

import { useMemo } from "react";

interface UserAvatarProps {
  fullName?: string | null;
  email?: string | null;
  showName?: boolean;
  size?: "xs" | "sm" | "md" | "lg" | "xl";
}

const SIZE_PX: Record<NonNullable<UserAvatarProps["size"]>, number> = {
  xs: 24,
  sm: 40,
  md: 48,
  lg: 64,
  xl: 80,
};

const SIZE_TEXT: Record<NonNullable<UserAvatarProps["size"]>, string> = {
  xs: "text-[10px]",
  sm: "text-sm",
  md: "text-base",
  lg: "text-lg",
  xl: "text-xl",
};

const PALETTE = [
  "bg-blue-600",
  "bg-emerald-600",
  "bg-violet-600",
  "bg-rose-600",
  "bg-amber-600",
  "bg-cyan-600",
  "bg-indigo-600",
  "bg-teal-600",
] as const;

function displayLabel(fullName?: string | null, email?: string | null): string {
  return fullName?.trim() || email?.trim() || "User";
}

/** Two characters from the name (e.g. "Jane Doe" → "JD", "admin" → "AD"). */
function initialsFrom(fullName?: string | null, email?: string | null): string {
  const name = fullName?.trim();
  if (name) {
    const parts = name.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
      return `${parts[0]![0]!}${parts[1]![0]!}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  }

  const mail = email?.trim();
  if (mail) {
    const local = mail.split("@")[0] ?? mail;
    return local.slice(0, 2).toUpperCase();
  }

  return "U";
}

function colorFromSeed(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  }
  return PALETTE[hash % PALETTE.length]!;
}

export function UserAvatar({
  fullName,
  email,
  showName = true,
  size = "sm",
}: UserAvatarProps) {
  const label = displayLabel(fullName, email);
  const initials = useMemo(() => initialsFrom(fullName, email), [fullName, email]);
  const bgClass = useMemo(
    () => colorFromSeed((email ?? fullName ?? "user").trim().toLowerCase()),
    [email, fullName],
  );
  const px = SIZE_PX[size];

  return (
    <div className="flex items-center gap-3">
      <span
        aria-hidden
        className={`inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white ${bgClass} ${SIZE_TEXT[size]}`}
        style={{ width: px, height: px }}
        title={label}
      >
        {initials}
      </span>
      {showName ? (
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{label}</span>
      ) : null}
    </div>
  );
}

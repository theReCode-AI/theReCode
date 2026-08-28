import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { deleteGitCredential, listGitCredentials, saveGitCredential } from "@/api/git";
import { ApiError } from "@/api/client";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import { useAuthStore } from "@/stores/authStore";
import type { GitProvider } from "@/types/project";
import { formatDateTime } from "@/utils/runStages";

export function SettingsPage() {
  const user = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();

  const [provider, setProvider] = useState<GitProvider>("github");
  const [accessToken, setAccessToken] = useState("");
  const [tokenLabel, setTokenLabel] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const credentialsQuery = useQuery({
    queryKey: ["git-credentials"],
    queryFn: () => listGitCredentials(token!),
    enabled: Boolean(token),
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      saveGitCredential(
        {
          provider,
          access_token: accessToken,
          token_label: tokenLabel.trim() || undefined,
        },
        token!,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["git-credentials"] });
      setAccessToken("");
      setTokenLabel("");
      setFormError(null);
    },
    onError: (error: unknown) => {
      setFormError(error instanceof ApiError ? error.detail ?? error.message : "Failed to save token.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (credentialProvider: GitProvider) => deleteGitCredential(credentialProvider, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["git-credentials"] });
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    if (!accessToken.trim()) {
      setFormError("Access token is required.");
      return;
    }
    saveMutation.mutate();
  }

  return (
    <section>
      <PageHeader
        title="Settings"
        subtitle="Account preferences and Git provider access tokens."
      />

      <section className="panel">
        <h2>Account</h2>
        <dl className="settings-list">
          <div>
            <dt>Name</dt>
            <dd>{user?.full_name}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{user?.email}</dd>
          </div>
        </dl>
      </section>

      <section className="panel form-panel">
        <h2>Git credentials</h2>
        <p className="page-subtitle">
          Save a GitHub or GitLab personal access token before cloning repositories or creating pull
          requests. Tokens are encrypted on the server and never shown again after saving.
        </p>

        {credentialsQuery.isLoading ? <LoadingState /> : null}
        {credentialsQuery.isError ? (
          <ErrorState message="Unable to load saved Git credentials." />
        ) : null}

        {credentialsQuery.data && credentialsQuery.data.length > 0 ? (
          <ul className="simple-list git-credential-list">
            {credentialsQuery.data.map((credential) => (
              <li key={credential.id} className="git-credential-item">
                <div>
                  <strong>{credential.provider}</strong>
                  {credential.token_label ? ` · ${credential.token_label}` : ""}
                  <div className="page-subtitle">
                    Updated {formatDateTime(credential.updated_at)}
                  </div>
                </div>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate(credential.provider)}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        ) : credentialsQuery.isSuccess ? (
          <EmptyState message="No Git credentials saved yet." />
        ) : null}

        <form className="form-grid" onSubmit={handleSubmit}>
          <label>
            Provider
            <select
              value={provider}
              onChange={(event) => setProvider(event.target.value as GitProvider)}
            >
              <option value="github">GitHub</option>
              <option value="gitlab">GitLab</option>
            </select>
          </label>
          <label>
            Label (optional)
            <input
              placeholder="e.g. dev laptop"
              value={tokenLabel}
              onChange={(event) => setTokenLabel(event.target.value)}
              autoComplete="off"
            />
          </label>
          <label className="full-width">
            Personal access token
            <input
              type="password"
              placeholder={provider === "github" ? "ghp_..." : "glpat-..."}
              value={accessToken}
              onChange={(event) => setAccessToken(event.target.value)}
              autoComplete="off"
              required
            />
          </label>
          {formError ? <p className="form-error full-width">{formError}</p> : null}
          <div className="full-width">
            <button type="submit" className="primary-button" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "Saving..." : "Save Git token"}
            </button>
          </div>
        </form>
      </section>
    </section>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Label, Select, TextInput } from "flowbite-react";
import { FormEvent, useState } from "react";

import { deleteGitCredential, listGitCredentials, saveGitCredential } from "@/api/git";
import {
  deleteGeminiCredential,
  getGeminiCredential,
  saveGeminiCredential,
} from "@/api/settings";
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

  const [geminiApiKey, setGeminiApiKey] = useState("");
  const [geminiKeyLabel, setGeminiKeyLabel] = useState("");
  const [geminiFormError, setGeminiFormError] = useState<string | null>(null);

  const credentialsQuery = useQuery({
    queryKey: ["git-credentials"],
    queryFn: () => listGitCredentials(token!),
    enabled: Boolean(token),
  });

  const geminiQuery = useQuery({
    queryKey: ["gemini-credential"],
    queryFn: () => getGeminiCredential(token!),
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

  const saveGeminiMutation = useMutation({
    mutationFn: () =>
      saveGeminiCredential(
        {
          api_key: geminiApiKey.trim(),
          key_label: geminiKeyLabel.trim() || undefined,
        },
        token!,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["gemini-credential"] });
      setGeminiApiKey("");
      setGeminiKeyLabel("");
      setGeminiFormError(null);
    },
    onError: (error: unknown) => {
      setGeminiFormError(
        error instanceof ApiError ? error.detail ?? error.message : "Failed to save Gemini API key.",
      );
    },
  });

  const deleteGeminiMutation = useMutation({
    mutationFn: () => deleteGeminiCredential(token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["gemini-credential"] });
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

  function handleGeminiSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setGeminiFormError(null);
    if (!geminiApiKey.trim()) {
      setGeminiFormError("Gemini API key is required.");
      return;
    }
    saveGeminiMutation.mutate();
  }

  return (
    <section>
      <PageHeader
        title="Settings"
        subtitle="Account preferences, Gemini API key, and Git provider access tokens."
      />

      <Card className="mb-4">
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Account</h2>
        <dl className="grid gap-3 text-sm">
          <div>
            <dt className="text-gray-500 dark:text-gray-400">Name</dt>
            <dd className="font-medium text-gray-900 dark:text-white">{user?.full_name}</dd>
          </div>
          <div>
            <dt className="text-gray-500 dark:text-gray-400">Email</dt>
            <dd className="font-medium text-gray-900 dark:text-white">{user?.email}</dd>
          </div>
        </dl>
      </Card>

      <Card className="mb-4">
        <h2 className="mb-2 text-lg font-semibold text-gray-900 dark:text-white">Gemini API key</h2>
        <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
          Save your Google AI Studio Gemini API key for chat, code fixes, and the autonomous
          pipeline. The key is encrypted on the server and never shown again after saving. Get a key
          from{" "}
          <a
            href="https://aistudio.google.com/apikey"
            target="_blank"
            rel="noreferrer"
            className="text-blue-600 hover:underline"
          >
            Google AI Studio
          </a>
          .
        </p>

        {geminiQuery.isLoading ? <LoadingState /> : null}
        {geminiQuery.isError ? (
          <ErrorState message="Unable to load Gemini API key status." />
        ) : null}

        {geminiQuery.data ? (
          <div className="mb-6 flex items-center justify-between gap-4 rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-900">
            <div>
              <strong className="text-gray-900 dark:text-white">
                Gemini key configured
                {geminiQuery.data.key_label ? ` · ${geminiQuery.data.key_label}` : ""}
              </strong>
              <div className="text-sm text-gray-500 dark:text-gray-400">
                Updated {formatDateTime(geminiQuery.data.updated_at)}
              </div>
            </div>
            <Button
              color="light"
              size="sm"
              disabled={deleteGeminiMutation.isPending}
              onClick={() => deleteGeminiMutation.mutate()}
            >
              Remove
            </Button>
          </div>
        ) : geminiQuery.isSuccess ? (
          <EmptyState message="No Gemini API key saved yet." />
        ) : null}

        <form className="grid gap-4 sm:grid-cols-2" onSubmit={handleGeminiSubmit}>
          <div>
            <Label htmlFor="geminiKeyLabel">Label (optional)</Label>
            <TextInput
              id="geminiKeyLabel"
              placeholder="e.g. personal studio key"
              value={geminiKeyLabel}
              onChange={(event) => setGeminiKeyLabel(event.target.value)}
              autoComplete="off"
            />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="geminiApiKey">Gemini API key</Label>
            <TextInput
              id="geminiApiKey"
              type="password"
              placeholder="AIza..."
              value={geminiApiKey}
              onChange={(event) => setGeminiApiKey(event.target.value)}
              autoComplete="off"
              required
            />
          </div>
          {geminiFormError ? (
            <div className="sm:col-span-2">
              <Alert color="failure">{geminiFormError}</Alert>
            </div>
          ) : null}
          <div className="sm:col-span-2">
            <Button type="submit" disabled={saveGeminiMutation.isPending}>
              {saveGeminiMutation.isPending
                ? "Saving..."
                : geminiQuery.data
                  ? "Replace Gemini key"
                  : "Save Gemini key"}
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <h2 className="mb-2 text-lg font-semibold text-gray-900 dark:text-white">Git credentials</h2>
        <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
          Save a GitHub or GitLab personal access token before cloning repositories or creating pull
          requests. Tokens are encrypted on the server and never shown again after saving.
        </p>

        {credentialsQuery.isLoading ? <LoadingState /> : null}
        {credentialsQuery.isError ? (
          <ErrorState message="Unable to load saved Git credentials." />
        ) : null}

        {credentialsQuery.data && credentialsQuery.data.length > 0 ? (
          <ul className="mb-6 space-y-3">
            {credentialsQuery.data.map((credential) => (
              <li
                key={credential.id}
                className="flex items-center justify-between gap-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 p-3"
              >
                <div>
                  <strong className="text-gray-900 dark:text-white">{credential.provider}</strong>
                  {credential.token_label ? ` · ${credential.token_label}` : ""}
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    Updated {formatDateTime(credential.updated_at)}
                  </div>
                </div>
                <Button
                  color="light"
                  size="sm"
                  disabled={deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate(credential.provider)}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        ) : credentialsQuery.isSuccess ? (
          <EmptyState message="No Git credentials saved yet." />
        ) : null}

        <form className="grid gap-4 sm:grid-cols-2" onSubmit={handleSubmit}>
          <div>
            <Label htmlFor="gitProvider">Provider</Label>
            <Select
              id="gitProvider"
              value={provider}
              onChange={(event) => setProvider(event.target.value as GitProvider)}
            >
              <option value="github">GitHub</option>
              <option value="gitlab">GitLab</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="tokenLabel">Label (optional)</Label>
            <TextInput
              id="tokenLabel"
              placeholder="e.g. dev laptop"
              value={tokenLabel}
              onChange={(event) => setTokenLabel(event.target.value)}
              autoComplete="off"
            />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="accessToken">Personal access token</Label>
            <TextInput
              id="accessToken"
              type="password"
              placeholder={provider === "github" ? "ghp_..." : "glpat-..."}
              value={accessToken}
              onChange={(event) => setAccessToken(event.target.value)}
              autoComplete="off"
              required
            />
          </div>
          {formError ? (
            <div className="sm:col-span-2">
              <Alert color="failure">{formError}</Alert>
            </div>
          ) : null}
          <div className="sm:col-span-2">
            <Button type="submit" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "Saving..." : "Save Git token"}
            </Button>
          </div>
        </form>
      </Card>
    </section>
  );
}

import { Alert, Button, Card, Label, TextInput } from "flowbite-react";
import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { useAuthStore } from "@/stores/authStore";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((state) => state.login);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const redirectTo =
    (location.state as { from?: string } | null)?.from ?? "/dashboard";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login({ email, password });
      navigate(redirectTo, { replace: true });
    } catch (submitError) {
      const message =
        submitError instanceof ApiError
          ? submitError.detail ?? submitError.message
          : "Unable to sign in.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthLayout>
      <Card className="border border-white/10 bg-white/10 shadow-2xl shadow-black/20 backdrop-blur-md">
        <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
          <div className="text-center lg:text-left">
            <h1 className="text-2xl font-bold tracking-tight text-white">Welcome back</h1>
            <p className="mt-1.5 text-sm text-slate-300">
              Sign in to monitor autonomous engineering runs.
            </p>
          </div>

          <div>
            <Label htmlFor="email" className="mb-1.5 text-slate-200">
              Email
            </Label>
            <TextInput
              id="email"
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              sizing="lg"
            />
          </div>

          <div>
            <Label htmlFor="password" className="mb-1.5 text-slate-200">
              Password
            </Label>
            <TextInput
              id="password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              sizing="lg"
            />
          </div>

          {error ? <Alert color="failure">{error}</Alert> : null}

          <Button
            type="submit"
            color="blue"
            size="lg"
            className="w-full bg-gradient-to-r from-blue-600 to-blue-700"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Signing in..." : "Sign in"}
          </Button>

          <p className="text-center text-sm text-slate-400">
            New to theReCode?{" "}
            <Link
              to="/register"
              className="font-semibold text-blue-400 hover:text-blue-300 hover:underline"
            >
              Create an account
            </Link>
          </p>
        </form>
      </Card>
    </AuthLayout>
  );
}

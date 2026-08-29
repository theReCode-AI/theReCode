import { Alert, Button, Card, Label, TextInput } from "flowbite-react";
import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { useAuthStore } from "@/stores/authStore";

export function RegisterPage() {
  const navigate = useNavigate();
  const register = useAuthStore((state) => state.register);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await register({ email, full_name: fullName, password });
      navigate("/dashboard", { replace: true });
    } catch (submitError) {
      const message =
        submitError instanceof ApiError
          ? submitError.detail ?? submitError.message
          : "Unable to create account.";
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
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Create your account
            </h1>
            <p className="mt-1.5 text-sm text-slate-300">
              Start orchestrating autonomous repository runs.
            </p>
          </div>

          <div>
            <Label htmlFor="fullName" className="mb-1.5 text-slate-200">
              Full name
            </Label>
            <TextInput
              id="fullName"
              type="text"
              placeholder="Jane Smith"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              required
              sizing="lg"
            />
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
              placeholder="At least 8 characters"
              value={password}
              minLength={8}
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
            className="w-full bg-gradient-to-r from-blue-600 to-emerald-600"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Creating account..." : "Create account"}
          </Button>

          <p className="text-center text-sm text-slate-400">
            Already have an account?{" "}
            <Link
              to="/login"
              className="font-semibold text-blue-400 hover:text-blue-300 hover:underline"
            >
              Sign in
            </Link>
          </p>
        </form>
      </Card>
    </AuthLayout>
  );
}

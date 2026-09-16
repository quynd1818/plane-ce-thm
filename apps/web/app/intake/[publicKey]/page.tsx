import { useEffect, useState, type FormEvent } from "react";
import { PageHead } from "@/components/core/page-title";
import {
  projectPhase3Service,
  type TIntakeForm,
} from "@/services/project/phase3.service";

type FormValues = Record<string, string>;

function PublicIntakeFormPage({ params }: { params: { publicKey: string } }) {
  const [form, setForm] = useState<TIntakeForm | null>(null);
  const [values, setValues] = useState<FormValues>({});
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    void projectPhase3Service
      .getPublicIntakeForm(params.publicKey)
      .then((data) => {
        setForm(data);
        setValues(
          Object.fromEntries(
            data.fields.map((field) => [String(field.key ?? ""), String(data.default_values[String(field.key ?? "")] ?? "")])
          )
        );
        return data;
      })
      .catch(() => setError("This intake form is not available."));
  }, [params.publicKey]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form) return;
    setSubmitting(true);
    setError("");
    try {
      await projectPhase3Service.submitPublicIntakeForm(params.publicKey, values);
      setSubmitted(true);
    } catch {
      setError("We could not submit this request. Please check the required fields and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-surface-1 px-6">
        <div className="w-full max-w-xl rounded-lg border border-subtle-1 bg-surface-2 p-8 text-center">
          <h1 className="text-2xl font-semibold">Request submitted</h1>
          <p className="mt-2 text-sm text-tertiary">Thank you. Your request has been added to the project intake inbox.</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-surface-1 px-6 py-12">
      <PageHead title={form?.name ?? "Intake form"} />
      <div className="mx-auto w-full max-w-2xl rounded-lg border border-subtle-1 bg-surface-2 p-8">
        {form ? (
          <>
            <h1 className="text-2xl font-semibold">{form.name}</h1>
            {form.description && <p className="mt-2 text-sm text-tertiary">{form.description}</p>}
            <form className="mt-8 space-y-5" onSubmit={submit}>
              {form.fields.map((field) => {
                const key = String(field.key ?? "");
                const label = String(field.label ?? key);
                const type = String(field.type ?? "text");
                const required = Boolean(field.required);
                const options = Array.isArray(field.options) ? field.options.map(String) : [];
                return (
                  <label key={key} className="block space-y-1">
                    <span className="text-sm font-medium">{label}{required && " *"}</span>
                    {type === "textarea" ? (
                      <textarea
                        className="min-h-28 w-full rounded border border-subtle-1 bg-surface-1 px-3 py-2"
                        required={required}
                        value={values[key] ?? ""}
                        onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))}
                      />
                    ) : type === "select" ? (
                      <select
                        className="w-full rounded border border-subtle-1 bg-surface-1 px-3 py-2"
                        required={required}
                        value={values[key] ?? ""}
                        onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))}
                      >
                        <option value="">Select an option</option>
                        {options.map((option) => <option key={option} value={option}>{option}</option>)}
                      </select>
                    ) : (
                      <input
                        className="w-full rounded border border-subtle-1 bg-surface-1 px-3 py-2"
                        type={type === "number" || type === "date" || type === "email" ? type : "text"}
                        required={required}
                        value={values[key] ?? ""}
                        onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))}
                      />
                    )}
                  </label>
                );
              })}
              {error && <p className="text-sm text-danger-primary">{error}</p>}
              <button className="rounded bg-accent-primary px-4 py-2 text-on-color disabled:opacity-50" disabled={submitting} type="submit">
                {submitting ? "Submitting..." : "Submit request"}
              </button>
            </form>
          </>
        ) : (
          <p className={error ? "text-danger-primary" : "text-tertiary"}>{error || "Loading form..."}</p>
        )}
      </div>
    </main>
  );
}

export default PublicIntakeFormPage;

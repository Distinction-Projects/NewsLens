import { createClient } from "../../utils/supabase/server";

export default async function SupabaseTestPage() {
  const supabase = createClient();
  const { data: todos, error } = await supabase.from("todos").select("id,name").limit(25);

  return (
    <main>
      <h1>Supabase Test</h1>
      <p className="muted">Server-side read from the <code>todos</code> table.</p>
      {error ? (
        <div className="panel">
          <h2>Query Error</h2>
          <p>{error.message}</p>
        </div>
      ) : (
        <div className="panel">
          <h2>Todos</h2>
          {!todos?.length ? (
            <p className="muted">No rows found.</p>
          ) : (
            <ul>
              {todos.map((todo) => (
                <li key={todo.id}>{todo.name}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </main>
  );
}


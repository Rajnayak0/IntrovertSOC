import { useCallback, useEffect, useState } from 'react';

import { ApiError } from '../api/client';
import { knowledgeApi } from '../api/endpoints';
import type { KbHit, KnowledgeItem } from '../api/endpoints';
import { useAuth } from '../auth';

export function Knowledge() {
  const { me } = useAuth();
  const canEdit = me?.role === 'admin' || me?.role === 'analyst';

  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [hits, setHits] = useState<KbHit[] | null>(null);
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [tags, setTags] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const page = await knowledgeApi.list();
      setItems(page.results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load knowledge base');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runSearch = async () => {
    const q = query.trim();
    if (!q) {
      setHits(null);
      return;
    }
    setSearching(true);
    setError('');
    try {
      const res = await knowledgeApi.search(q);
      setHits(res.results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Search failed');
    } finally {
      setSearching(false);
    }
  };

  const addItem = async () => {
    if (!title.trim()) return;
    setError('');
    try {
      const created = await knowledgeApi.create({
        title: title.trim(),
        body,
        tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
      });
      setItems((prev) => [created, ...prev]);
      setShowAdd(false);
      setTitle('');
      setBody('');
      setTags('');
      setNote(`Added “${created.title}”`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to add item');
    }
  };

  const removeItem = async (item: KnowledgeItem) => {
    setError('');
    try {
      await knowledgeApi.remove(item.id);
      setItems((prev) => prev.filter((i) => i.id !== item.id));
      setHits((prev) => (prev ? prev.filter((h) => h.id !== item.id) : prev));
      setNote(`Deleted “${item.title}”`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Delete failed');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-1 min-w-64 gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void runSearch()}
            placeholder="Search (retrieval test) — keyword proposal + local scoring…"
            className="flex-1 rounded-md border border-edge bg-panel2 px-3 py-1.5 text-xs text-ink placeholder:text-faint focus:border-accent"
          />
          <button
            type="button"
            onClick={() => void runSearch()}
            disabled={searching}
            className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink hover:opacity-90 disabled:opacity-50"
          >
            {searching ? 'Searching…' : 'Search'}
          </button>
          {query && (
            <button
              type="button"
              onClick={() => {
                setQuery('');
                setHits(null);
              }}
              className="rounded-md border border-edge px-3 py-1.5 text-xs text-muted hover:text-ink"
            >
              Clear
            </button>
          )}
        </div>
        {canEdit && (
          <button
            type="button"
            onClick={() => setShowAdd((v) => !v)}
            className="rounded-md border border-edge px-3 py-1.5 text-xs text-ink hover:border-accent"
          >
            {showAdd ? 'Cancel' : '+ Add item'}
          </button>
        )}
        <span className="ml-auto text-xs text-faint">
          {hits !== null ? `${hits.length} hit(s)` : `${items.length} item(s)`}
        </span>
      </div>

      {error && (
        <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{error}</div>
      )}
      {note && (
        <div className="rounded-md border border-ok/40 bg-ok/10 px-3 py-2 text-xs text-ok">{note}</div>
      )}

      {showAdd && (
        <div className="space-y-2 rounded-lg border border-edge bg-panel p-4">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Title (required)"
            className="w-full rounded-md border border-edge bg-panel2 px-3 py-1.5 text-xs text-ink placeholder:text-faint focus:border-accent"
          />
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="What did we learn? (2–6 sentences)"
            rows={3}
            className="w-full rounded-md border border-edge bg-panel2 px-3 py-1.5 text-xs text-ink placeholder:text-faint focus:border-accent"
          />
          <div className="flex items-center gap-2">
            <input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="tags, comma, separated"
              className="flex-1 rounded-md border border-edge bg-panel2 px-3 py-1.5 text-xs text-ink placeholder:text-faint focus:border-accent"
            />
            <button
              type="button"
              onClick={() => void addItem()}
              className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink hover:opacity-90"
            >
              Save
            </button>
          </div>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {(hits ?? items.map((i) => ({ id: i.id, title: i.title, body: i.body, tags: i.tags, score: 0 }))).map((h) => (
          <div key={h.id} className="group rounded-lg border border-edge bg-panel p-4">
            <div className="flex items-start justify-between gap-2">
              <h3 className="text-sm font-semibold text-ink">{h.title}</h3>
              <div className="flex items-center gap-2">
                {hits !== null && (
                  <span className="font-mono text-[10px] text-accent" title="retrieval score">
                    {h.score}
                  </span>
                )}
                {canEdit && (
                  <button
                    type="button"
                    onClick={() => {
                      const item = items.find((i) => i.id === h.id);
                      if (item) void removeItem(item);
                    }}
                    className="text-[11px] text-faint opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
                    title="Delete"
                  >
                    delete
                  </button>
                )}
              </div>
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-muted">{h.body}</p>
            <div className="mt-2 flex flex-wrap gap-1">
              {h.tags.map((t) => (
                <span key={t} className="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] text-accent">
                  {t}
                </span>
              ))}
            </div>
          </div>
        ))}
        {(hits ?? items).length === 0 && (
          <div className="rounded-lg border border-dashed border-edge px-4 py-8 text-center text-xs text-faint md:col-span-2">
            {hits !== null
              ? 'No knowledge matches this query.'
              : 'Knowledge base is empty — close a case to auto-extract, or add an item.'}
          </div>
        )}
      </div>
    </div>
  );
}

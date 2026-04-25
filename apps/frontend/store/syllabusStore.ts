import { create } from 'zustand';

/**
 * Slim MPFE-aligned syllabus store.
 *
 * Mirrors the Supabase schema:
 *  - `syllabuses`  (one per thread)
 *  - `chapters`    (N per syllabus)
 *  - `lessons`     (N per chapter, Markdown body in `content_markdown`)
 *  - `activities`  (0..N per chapter, JSON quiz payload)
 *
 * State is per-thread (`byThread`) so switching threads instantly swaps the
 * file tree without a flicker. The hook consumers only read the
 * top-level mirror fields (`syllabus`, `chapters`, `lessons`, `activities`,
 * `activeItemId`, `expandedChapterIds`).
 *
 * Writers live elsewhere (the agent + direct DB writes from curriculum-mcp);
 * realtime subscriptions call `applyRemote*` / `removeBy*` to keep us in sync.
 */

export interface Syllabus {
  id: string;
  thread_id: string | null;
  title: string;
  description?: string | null;
}

export interface Chapter {
  id: string;
  syllabus_id: string;
  title: string;
  summary?: string | null;
  position: number;
  status?: string | null;
}

export interface Lesson {
  id: string;
  chapter_id: string;
  syllabus_id: string;
  title: string;
  position: number;
  content_markdown: string | null;
  substep_id?: string | null;
  version?: number;
  needs_review?: boolean | null;
  last_author?: string | null;
  draft_attempts?: number | null;
}

export type ActivityKind = 'quiz';

export interface QuizQuestion {
  prompt: string;
  options: string[];
  correct_index: number;
  explanation?: string;
  difficulty?: 'easy' | 'medium' | 'hard' | string;
}

export interface QuizActivityPayload {
  kind: ActivityKind;
  instructions?: string;
  questions: QuizQuestion[];
  summary?: string;
}

export interface Activity {
  id: string;
  chapter_id: string;
  syllabus_id: string;
  lesson_id?: string | null;
  title: string | null;
  position: number;
  payload: QuizActivityPayload;
  substep_id?: string | null;
  draft_attempts?: number | null;
}

interface ThreadSlice {
  syllabus: Syllabus | null;
  chapters: Chapter[];
  lessons: Lesson[];
  activities: Activity[];
  activeItemId: string | null;
  expandedChapterIds: Set<string>;
}

const DEFAULT_BUCKET = '__default__';

const emptySlice = (): ThreadSlice => ({
  syllabus: null,
  chapters: [],
  lessons: [],
  activities: [],
  activeItemId: null,
  expandedChapterIds: new Set(),
});

export type ActiveItem =
  | { kind: 'lesson'; lesson: Lesson }
  | { kind: 'activity'; activity: Activity }
  | null;

interface SyllabusStore extends ThreadSlice {
  byThread: Record<string, ThreadSlice>;
  currentThreadId: string | null;

  // thread bucket management
  setCurrentThread: (threadId: string | null) => void;
  resetThread: (threadId?: string | null) => void;

  // selection / UI
  setActiveItem: (id: string | null) => void;
  toggleChapter: (chapterId: string) => void;
  getActiveItem: () => ActiveItem;
  getActiveLesson: () => Lesson | null;
  getActiveActivity: () => Activity | null;

  // realtime upserts (called from useSyllabusRealtime)
  applyRemoteSyllabus: (row: Partial<Syllabus> & { id: string }) => void;
  removeSyllabusById: (id: string) => void;
  applyRemoteChapter: (row: Partial<Chapter> & { id: string; syllabus_id: string }) => void;
  removeChapterById: (id: string) => void;
  applyRemoteLesson: (row: Partial<Lesson> & { id: string; chapter_id: string }) => void;
  removeLessonById: (id: string) => void;
  applyRemoteActivity: (row: Partial<Activity> & { id: string; chapter_id: string }) => void;
  removeActivityById: (id: string) => void;

  // bulk seed (initial fetch)
  hydrate: (payload: {
    syllabus: Syllabus | null;
    chapters: Chapter[];
    lessons: Lesson[];
    activities: Activity[];
  }) => void;
}

function keyOf(state: { currentThreadId: string | null }): string {
  return state.currentThreadId ?? DEFAULT_BUCKET;
}

function updateSlice(
  state: SyllabusStore,
  updater: (slice: ThreadSlice) => ThreadSlice
): Partial<SyllabusStore> {
  const key = keyOf(state);
  const current = state.byThread[key] ?? emptySlice();
  const next = updater(current);
  return {
    byThread: { ...state.byThread, [key]: next },
    syllabus: next.syllabus,
    chapters: next.chapters,
    lessons: next.lessons,
    activities: next.activities,
    activeItemId: next.activeItemId,
    expandedChapterIds: next.expandedChapterIds,
  };
}

function upsertSorted<T extends { id: string; position?: number }>(
  list: T[],
  row: T
): T[] {
  const idx = list.findIndex((x) => x.id === row.id);
  const merged = idx >= 0 ? [...list.slice(0, idx), { ...list[idx], ...row }, ...list.slice(idx + 1)] : [...list, row];
  return merged.sort((a, b) => (a.position ?? 0) - (b.position ?? 0));
}

export const useSyllabusStore = create<SyllabusStore>()((set, get) => ({
  byThread: {},
  currentThreadId: null,
  syllabus: null,
  chapters: [],
  lessons: [],
  activities: [],
  activeItemId: null,
  expandedChapterIds: new Set(),

  setCurrentThread: (threadId) =>
    set((state) => {
      const key = threadId ?? DEFAULT_BUCKET;
      const slice = state.byThread[key] ?? emptySlice();
      const byThread = state.byThread[key]
        ? state.byThread
        : { ...state.byThread, [key]: slice };
      return {
        currentThreadId: threadId,
        byThread,
        syllabus: slice.syllabus,
        chapters: slice.chapters,
        lessons: slice.lessons,
        activities: slice.activities,
        activeItemId: slice.activeItemId,
        expandedChapterIds: slice.expandedChapterIds,
      };
    }),

  resetThread: (threadId) =>
    set((state) => {
      const key = threadId ?? keyOf(state);
      const byThread = { ...state.byThread, [key]: emptySlice() };
      const isActive = key === keyOf(state);
      return isActive
        ? {
            byThread,
            syllabus: null,
            chapters: [],
            lessons: [],
            activities: [],
            activeItemId: null,
            expandedChapterIds: new Set(),
          }
        : { byThread };
    }),

  setActiveItem: (id) =>
    set((state) =>
      updateSlice(state, (slice) => ({ ...slice, activeItemId: id }))
    ),

  toggleChapter: (chapterId) =>
    set((state) =>
      updateSlice(state, (slice) => {
        const next = new Set(slice.expandedChapterIds);
        if (next.has(chapterId)) next.delete(chapterId);
        else next.add(chapterId);
        return { ...slice, expandedChapterIds: next };
      })
    ),

  getActiveItem: () => {
    const { activeItemId, lessons, activities } = get();
    if (!activeItemId) return null;
    const lesson = lessons.find((l) => l.id === activeItemId);
    if (lesson) return { kind: 'lesson', lesson };
    const activity = activities.find((a) => a.id === activeItemId);
    if (activity) return { kind: 'activity', activity };
    return null;
  },

  getActiveLesson: () => {
    const item = get().getActiveItem();
    return item?.kind === 'lesson' ? item.lesson : null;
  },

  getActiveActivity: () => {
    const item = get().getActiveItem();
    return item?.kind === 'activity' ? item.activity : null;
  },

  applyRemoteSyllabus: (row) =>
    set((state) =>
      updateSlice(state, (slice) => ({
        ...slice,
        syllabus: {
          id: row.id,
          thread_id: row.thread_id ?? slice.syllabus?.thread_id ?? null,
          title: row.title ?? slice.syllabus?.title ?? '',
          description: row.description ?? slice.syllabus?.description ?? null,
        },
      }))
    ),

  removeSyllabusById: (id) =>
    set((state) =>
      updateSlice(state, (slice) =>
        slice.syllabus?.id === id ? emptySlice() : slice
      )
    ),

  applyRemoteChapter: (row) =>
    set((state) =>
      updateSlice(state, (slice) => ({
        ...slice,
        chapters: upsertSorted(slice.chapters, {
          id: row.id,
          syllabus_id: row.syllabus_id,
          title: row.title ?? '',
          summary: row.summary ?? null,
          position: row.position ?? 0,
          status: row.status ?? null,
        }),
      }))
    ),

  removeChapterById: (id) =>
    set((state) =>
      updateSlice(state, (slice) => ({
        ...slice,
        chapters: slice.chapters.filter((c) => c.id !== id),
        lessons: slice.lessons.filter((l) => l.chapter_id !== id),
        activities: slice.activities.filter((a) => a.chapter_id !== id),
      }))
    ),

  applyRemoteLesson: (row) =>
    set((state) =>
      updateSlice(state, (slice) => {
        const existing = slice.lessons.find((l) => l.id === row.id);
        const merged: Lesson = {
          ...(existing ?? {
            id: row.id,
            chapter_id: row.chapter_id,
            syllabus_id: row.syllabus_id ?? slice.syllabus?.id ?? '',
            title: '',
            position: 0,
            content_markdown: null,
          }),
          ...row,
        } as Lesson;
        return { ...slice, lessons: upsertSorted(slice.lessons, merged) };
      })
    ),

  removeLessonById: (id) =>
    set((state) =>
      updateSlice(state, (slice) => ({
        ...slice,
        lessons: slice.lessons.filter((l) => l.id !== id),
        activeItemId: slice.activeItemId === id ? null : slice.activeItemId,
      }))
    ),

  applyRemoteActivity: (row) =>
    set((state) =>
      updateSlice(state, (slice) => {
        const existing = slice.activities.find((a) => a.id === row.id);
        const merged: Activity = {
          ...(existing ?? {
            id: row.id,
            chapter_id: row.chapter_id,
            syllabus_id: row.syllabus_id ?? slice.syllabus?.id ?? '',
            lesson_id: null,
            title: null,
            position: 0,
            payload: { kind: 'quiz', questions: [] },
          }),
          ...row,
        } as Activity;
        return { ...slice, activities: upsertSorted(slice.activities, merged) };
      })
    ),

  removeActivityById: (id) =>
    set((state) =>
      updateSlice(state, (slice) => ({
        ...slice,
        activities: slice.activities.filter((a) => a.id !== id),
        activeItemId: slice.activeItemId === id ? null : slice.activeItemId,
      }))
    ),

  hydrate: ({ syllabus, chapters, lessons, activities }) =>
    set((state) =>
      updateSlice(state, (slice) => ({
        ...slice,
        syllabus,
        chapters: [...chapters].sort((a, b) => (a.position ?? 0) - (b.position ?? 0)),
        lessons: [...lessons].sort((a, b) => (a.position ?? 0) - (b.position ?? 0)),
        activities: [...activities].sort((a, b) => (a.position ?? 0) - (b.position ?? 0)),
      }))
    ),
}));

import { useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

const today = new Date().toISOString().slice(0, 10);

export default function DailyPlan() {
  const queryClient = useQueryClient();
  const debounceRef = useRef(null);
  const initialized = useRef(false);

  const { data: queryData } = useQuery({
    queryKey: ['daily-plan', today],
    queryFn: () => api.getDailyPlan(today).then((d) => d.content),
    staleTime: Infinity,
  });

  // Initialize from cache immediately if prefetched, otherwise wait for load
  const [content, setContent] = useState(() => queryData ?? '');

  useEffect(() => {
    if (queryData !== undefined && !initialized.current) {
      setContent(queryData);
      initialized.current = true;
    }
  }, [queryData]);

  function handleChange(e) {
    const val = e.target.value;
    setContent(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      api.updateDailyPlan(today, val);
      queryClient.setQueryData(['daily-plan', today], val);
    }, 600);
  }

  return (
    <div className="daily-plan-area">
      <textarea
        className="daily-plan-textarea"
        value={content}
        onChange={handleChange}
        placeholder="What's the plan for today?"
      />
    </div>
  );
}

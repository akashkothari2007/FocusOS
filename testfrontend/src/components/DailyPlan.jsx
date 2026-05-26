import { useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

export default function DailyPlan() {
  const queryClient = useQueryClient();
  const debounceRef = useRef(null);
  const initialized = useRef(false);

  const { data: queryData } = useQuery({
    queryKey: ['plan'],
    queryFn: () => api.getPlan().then((d) => d.content),
    staleTime: Infinity,
  });

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
      api.updatePlan(val);
      queryClient.setQueryData(['plan'], val);
    }, 600);
  }

  return (
    <div className="daily-plan-area">
      <textarea
        className="daily-plan-textarea"
        value={content}
        onChange={handleChange}
        placeholder="What's the plan?"
      />
    </div>
  );
}

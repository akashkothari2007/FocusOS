import { useState, useEffect, useRef } from 'react';
import { api } from '../api';

const today = new Date().toISOString().slice(0, 10);

export default function DailyPlan() {
  const [content, setContent] = useState('');
  const debounceRef = useRef(null);

  useEffect(() => {
    api.getDailyPlan(today).then((d) => setContent(d.content));
  }, []);

  function handleChange(e) {
    const val = e.target.value;
    setContent(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      api.updateDailyPlan(today, val);
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

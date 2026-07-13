import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useWorkspaceStore = create(
  persist(
    (set, get) => ({
      items: [],
      
      addItem: (item) => {
        const exists = get().items.some(
          i => i.country === item.country && i.indicator === item.indicator
        );
        if (!exists) {
          const colors = ['#ff6b6b', '#ffd93d', '#6bcbff', '#ff6b9d', '#55efc4', '#ff9f43', '#a29bfe', '#fd79a8'];
          const colorIndex = get().items.length % colors.length;
          
          set((state) => ({
            items: [...state.items, { 
              ...item, 
              id: Date.now(),
              color: colors[colorIndex]
            }]
          }));
        }
      },
      
      removeItem: (id) => {
        set((state) => ({
          items: state.items.filter(item => item.id !== id)
        }));
      },
      
      clearAll: () => {
        set({ items: [] });
      }
    }),
    {
      name: 'workspace-storage',
    }
  )
);
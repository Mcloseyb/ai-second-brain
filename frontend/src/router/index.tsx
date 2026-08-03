/**
 * React Router 配置
 * ----------------
 * 4 个主要页面：智能笔记 / 知识问答 / 温故知新 / 回收站
 */
import { createHashRouter, Navigate } from 'react-router-dom'
import { lazy } from 'react'
import App from '@/App'

const NotesPage = lazy(() => import('@/pages/NotesPage'))
const ChatPage = lazy(() => import('@/pages/ChatPage'))
const ReviewPage = lazy(() => import('@/pages/ReviewPage'))
const TrashPage = lazy(() => import('@/pages/TrashPage'))

export const router = createHashRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Navigate to="/notes" replace /> },
      { path: 'notes', element: <NotesPage /> },
      { path: 'chat', element: <ChatPage /> },
      { path: 'review', element: <ReviewPage /> },
      { path: 'trash', element: <TrashPage /> },
    ],
  },
])

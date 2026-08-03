/**
 * React Router 配置
 * ----------------
 * 使用 Hash 路由（适配 Qt file:// 协议加载）。
 * 四个主要页面通过 React.lazy 懒加载。
 */
import { createHashRouter, Navigate } from 'react-router-dom'
import { lazy } from 'react'
import App from '@/App'

const NotesPage = lazy(() => import('@/pages/NotesPage'))
const ChatPage = lazy(() => import('@/pages/ChatPage'))
const QuizPage = lazy(() => import('@/pages/QuizPage'))
const MasteryPage = lazy(() => import('@/pages/MasteryPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const TrashPage = lazy(() => import('@/pages/TrashPage'))

export const router = createHashRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Navigate to="/notes" replace /> },
      { path: 'notes', element: <NotesPage /> },
      { path: 'chat', element: <ChatPage /> },
      { path: 'quiz', element: <QuizPage /> },
      { path: 'mastery', element: <MasteryPage /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'trash', element: <TrashPage /> },
    ],
  },
])

# AI Agent 学习笔记

## 什么是 Agent？

AI Agent（智能体）是一种能够**自主感知环境**、做出决策并执行动作的 AI 系统。

### 核心能力

1. **感知（Perception）**：接收用户输入和环境反馈
2. **推理（Reasoning）**：分析任务，拆解为可执行的步骤
3. **行动（Action）**：调用工具（搜索、计算、API 等）执行具体操作
4. **观察（Observation）**：获取工具执行结果，纳入下一步推理

## ReAct 模式

ReAct（Reasoning + Acting）是目前最主流的 Agent 推理范式：

- Thought: 当前我需要做什么？
- Action: 调用哪个工具？参数是什么？
- Observation: 工具返回了什么？

循环以上步骤，直到任务完成。

## 代码示例

```python
def agent_loop(task):
    while not task.is_done():
        thought = think(task)
        action = choose_action(thought)
        observation = execute(action)
        task.update(observation)
    return task.result()
```

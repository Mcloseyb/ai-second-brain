"""
Agent 基础设施 — ReAct 基类 + 工具注册机制（CLAUDE.md 13.5）
=============================================================
Agent = 角色(System Prompt) + 工具(Tools) + 推理(ReAct Loop) + 记忆(Context Window)

组成:
  - ToolDefinition   工具定义（名称 / 描述 / JSON Schema / 执行函数）
  - ToolRegistry     工具注册中心（register / schemas / execute）
  - BaseAgent        ReAct Agent 基类（循环调用 LLM + 工具，最多 max_steps 步）
  - AgentStep        单步执行记录（审计用）
  - AgentOutput      Agent 输出（内容 + 步骤 + token 统计）

使用示例（子类化或直接实例化）:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="search_note",
            description="按关键词搜索笔记",
            parameters={
                "type": "object",
                "properties": {"keyword": {"type": "string", "description": "搜索关键词"}},
                "required": ["keyword"],
            },
            func=search_note_impl,   # async def search_note_impl(keyword: str) -> str
        )
    )

    agent = BaseAgent(
        name="tag_agent",
        description="标签推荐",
        system_prompt="你是标签推荐助手...",
        tools=[registry],
    )
    output = await agent.run(user_input="为笔记推荐标签")
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from app.core.llm import llm_service

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class ToolDefinition:
    """工具定义 — OpenAI Function Calling 的 schema + 执行函数"""
    name: str
    description: str
    parameters: dict        # JSON Schema: {"type":"object","properties":{...},"required":[...]}
    func: Callable[..., Awaitable]  # async 执行函数（接收 **kwargs）


@dataclass
class AgentStep:
    """单步执行记录 — 用于审计日志与前端展示"""
    tool: str | None
    arguments: dict | None
    observation: str | None


@dataclass
class AgentOutput:
    """Agent 最终输出"""
    agent_name: str
    content: str                    # 最终回答文本（通常为 JSON）
    steps: list[AgentStep] = field(default_factory=list)
    tokens_used: int = 0            # 总 token 消耗（近似值）
    error: str | None = None        # 失败原因（降级时填充）


# ============================================================
# 工具注册中心
# ============================================================

class ToolRegistry:
    """工具注册与执行 — 每个 Agent 实例持有自己的 registry"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        """注册一个工具"""
        self._tools[definition.name] = definition

    @property
    def schemas(self) -> list[dict]:
        """转换为 OpenAI Function Calling 格式的 tools 列表"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def has(self, name: str) -> bool:
        return name in self._tools

    async def execute(self, name: str, arguments: dict) -> str:
        """
        执行工具并返回 JSON 字符串结果（Observation）

        Args:
            name: 工具名
            arguments: 工具参数 dict

        Returns:
            str: 工具执行结果（JSON 序列化），任何错误都以可读文本返回，
                 避免 ReAct 循环因工具异常中断
        """
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"工具 {name} 不存在"}, ensure_ascii=False)

        try:
            result = await tool.func(**arguments)
            return json.dumps(result, ensure_ascii=False, default=str)
        except TypeError as e:
            logger.warning(f"工具 {name} 参数错误: {e}")
            return json.dumps({"error": f"参数不正确: {e}"}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"工具 {name} 执行异常: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# ReAct Agent 基类
# ============================================================

class BaseAgent:
    """ReAct Agent 基类 — 角色 + 工具 + 推理循环"""

    name: str = "base"
    description: str = ""
    system_prompt: str = ""
    max_steps: int = 5          # ReAct 循环最大步数（防止死循环）
    temperature: float = 0.0    # 工具决策用低温

    def __init__(
        self,
        name: str | None = None,
        description: str | None = None,
        system_prompt: str | None = None,
        tools: list[ToolRegistry] | None = None,
        max_steps: int = 5,
    ) -> None:
        if name:
            self.name = name
        if description:
            self.description = description
        if system_prompt:
            self.system_prompt = system_prompt
        self.max_steps = max_steps
        # 合并多个 registry 到单一 registry
        self.registry = ToolRegistry()
        for reg in tools or []:
            for name_, tool in reg._tools.items():
                self.registry.register(tool)

    # ============================================================
    # ReAct 主循环
    # ============================================================
    async def run(self, user_input: str) -> AgentOutput:
        """
        执行 Agent 任务:
          while 未完成 and steps < max_steps:
              response = llm.chat_with_tools(messages, tools)
              if response has tool_calls:
                  执行工具 → observation → 追加消息 → 继续
              else:
                  返回最终内容
        """
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]
        steps: list[AgentStep] = []

        # 无工具 → 直接普通对话（不进入 ReAct 循环）
        if not self.registry.schemas:
            try:
                content = await llm_service.chat(messages, temperature=self.temperature)
                return AgentOutput(agent_name=self.name, content=content)
            except Exception as e:
                logger.error(f"Agent {self.name} LLM 调用失败: {e}")
                return AgentOutput(
                    agent_name=self.name, content="", error=str(e)
                )

        for step_idx in range(self.max_steps):
            try:
                msg = await llm_service.chat_with_tools(
                    messages,
                    tools=self.registry.schemas,
                    temperature=self.temperature,
                )
            except Exception as e:
                logger.error(f"Agent {self.name} 工具调用失败 (步 {step_idx}): {e}")
                return AgentOutput(
                    agent_name=self.name,
                    content="",
                    steps=steps,
                    error=f"LLM 调用失败: {e}",
                )

            # --- 模型决定调用工具 ---
            if msg.tool_calls:
                # 回填 assistant 消息（含 tool_calls，OpenAI 协议要求）
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    name = tc.function.name
                    try:
                        arguments = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        arguments = {}

                    logger.info(
                        f"Agent {self.name} 调用工具: {name} args={arguments}"
                    )
                    observation = await self.registry.execute(name, arguments)
                    steps.append(AgentStep(tool=name, arguments=arguments, observation=observation))

                    # tool 角色消息回填（OpenAI 协议）
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": observation,
                    })
                continue

            # --- 模型给出最终回答 ---
            content = msg.content or ""
            return AgentOutput(
                agent_name=self.name,
                content=content,
                steps=steps,
                tokens_used=0,  # 简化: 真实 token 需 LLM usage，后续可加
            )

        # 达到 max_steps 未收敛
        logger.warning(f"Agent {self.name} 达到最大步数 {self.max_steps}，未得到最终回答")
        return AgentOutput(
            agent_name=self.name,
            content="",
            steps=steps,
            error=f"超过最大步数 {self.max_steps}",
        )


# 便捷构造函数：通过 ToolDefinition 列表构建 Agent
def build_agent(
    name: str,
    description: str,
    system_prompt: str,
    tools: list[ToolDefinition],
    max_steps: int = 5,
) -> BaseAgent:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return BaseAgent(
        name=name,
        description=description,
        system_prompt=system_prompt,
        tools=[registry],
        max_steps=max_steps,
    )

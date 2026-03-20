"""Chat Orchestrator — Gemini Function Calling 기반 대화형 AI 비서."""

import json, uuid, logging
from datetime import datetime, timezone
from pathlib import Path
from google.genai import types
from .client import MODEL, get_gemini_client
from .chat_tools import CHAT_TOOLS, CHAT_TOOL_CONFIG

SYSTEM_PROMPT = """당신은 VisionFlow AI 비서입니다. 사용자의 업무 자동화를 도와줍니다.

역할:
- 워크플로우를 생성, 수정, 실행합니다
- 자연어 목표를 Computer Use로 즉시 실행합니다
- 실행 실패를 분석하고 수정 방법을 제안합니다
- 녹화를 시작/중지합니다

스텝 타입 우선순위 (워크플로우 생성 시 반드시 준수):
1. cmd — 셸 명령 (최우선)
2. hotkey — 단축키
3. clipboard_paste — 텍스트 입력
4. navigate — URL 이동
5. focus_window — 앱 창 활성화
6. vision_click — 동적 UI (최후 수단, on_failure=self_heal 권장)

항상 한국어로 대화하세요. 간결하고 친근하게.
워크플로우를 만들 때는 먼저 사용자에게 필요한 정보를 질문하세요.
실행 결과를 알려줄 때는 성공/실패 여부와 다음 단계를 안내하세요."""

class ChatOrchestrator:
    def __init__(self, storage, transport):
        self._storage = storage
        self._transport = transport

    async def process_message(self, session_id: str, user_message: str):
        """Process user message, yield SSE events (text chunks + function results)."""
        client = get_gemini_client()
        history = await self._load_history(session_id)

        # Add user message
        history.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

        # Generate with function calling
        max_fc_rounds = 5
        for _ in range(max_fc_rounds):
            response = await client.aio.models.generate_content(
                model=MODEL,
                contents=history,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=CHAT_TOOLS,
                    tool_config=CHAT_TOOL_CONFIG,
                    temperature=0.3,
                ),
            )

            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content:
                break

            history.append(candidate.content)

            # Extract function calls
            function_calls = [p for p in candidate.content.parts if p.function_call]

            if not function_calls:
                # Text response only - yield it
                text = "".join(p.text for p in candidate.content.parts if p.text)
                yield {"type": "text", "content": text}
                break

            # Execute function calls
            fc_responses = []
            for fc_part in function_calls:
                fc = fc_part.function_call
                result = await self._execute_function(fc.name, dict(fc.args) if fc.args else {})
                yield {"type": "function_call", "name": fc.name, "args": dict(fc.args) if fc.args else {}, "result": result}
                fc_responses.append(types.Part.from_function_response(name=fc.name, response=result))

            # Add function responses and continue loop
            history.append(types.Content(role="user", parts=fc_responses))

        # Save history
        await self._save_history(session_id, history)

    async def _execute_function(self, name: str, args: dict) -> dict:
        """Execute a chat function call."""
        try:
            if name == "list_workflows":
                return await self._fn_list_workflows()
            elif name == "get_workflow":
                return await self._fn_get_workflow(args["workflow_id"])
            elif name == "create_workflow":
                return await self._fn_create_workflow(args)
            elif name == "edit_step":
                return await self._fn_edit_step(args)
            elif name == "run_workflow":
                return await self._fn_run_workflow(args)
            elif name == "run_computer_use":
                return await self._fn_run_computer_use(args["goal"])
            elif name == "start_recording":
                return await self._fn_start_recording(args)
            elif name == "stop_recording":
                return await self._fn_stop_recording()
            elif name == "get_run_result":
                return await self._fn_get_run_result(args["run_id"])
            elif name == "analyze_failure":
                return await self._fn_analyze_failure(args["run_id"])
            else:
                return {"error": f"Unknown function: {name}"}
        except Exception as e:
            return {"error": str(e)}

    # -- Function implementations --

    async def _fn_list_workflows(self):
        wf_ids = await self._storage.list_dir("workflows")
        results = []
        for wid in wf_ids:
            wf = await self._storage.read_json(f"workflows/{wid}/latest.json")
            if wf:
                results.append({"workflow_id": wid, "name": wf.get("name",""), "step_count": len(wf.get("steps",[]))})
        return {"workflows": results}

    async def _fn_get_workflow(self, workflow_id):
        wf = await self._storage.read_json(f"workflows/{workflow_id}/latest.json")
        if not wf:
            return {"error": "워크플로우를 찾을 수 없습니다"}
        return wf

    async def _fn_create_workflow(self, args):
        workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
        steps = args.get("steps", [])
        for i, s in enumerate(steps, 1):
            s["id"] = i
            s.setdefault("timeout_sec", 10)
            s.setdefault("speed", "normal")
            s.setdefault("on_failure", "retry")
        wf = {
            "workflow_id": workflow_id,
            "name": args["name"],
            "description": args["description"],
            "version": 1,
            "default_speed": "normal",
            "steps": steps,
        }
        await self._storage.write_json(f"workflows/{workflow_id}/v1.json", wf)
        await self._storage.write_json(f"workflows/{workflow_id}/latest.json", wf)
        return {"workflow_id": workflow_id, "name": args["name"], "step_count": len(steps)}

    async def _fn_edit_step(self, args):
        wid = args["workflow_id"]
        step_id = args["step_id"]
        changes = args.get("changes", {})
        wf = await self._storage.read_json(f"workflows/{wid}/latest.json")
        if not wf:
            return {"error": "워크플로우를 찾을 수 없습니다"}
        for step in wf.get("steps", []):
            if step.get("id") == step_id:
                step.update(changes)
                break
        wf["version"] = wf.get("version", 1) + 1
        await self._storage.write_json(f"workflows/{wid}/latest.json", wf)
        return {"success": True, "workflow_id": wid, "step_id": step_id}

    async def _fn_run_workflow(self, args):
        from shared.ipc_models import AgentCommand
        wid = args["workflow_id"]
        mode = args.get("mode", "normal")
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        wf = await self._storage.read_json(f"workflows/{wid}/latest.json")
        if not wf:
            return {"error": "워크플로우를 찾을 수 없습니다"}
        meta = {
            "run_id": run_id, "workflow_id": wid, "workflow_name": wf.get("name",""),
            "status": "pending", "started_at": datetime.now(timezone.utc).isoformat(),
            "current_step": 0, "total_steps": len(wf.get("steps",[])), "mode": mode,
        }
        await self._storage.write_json(f"runs/{run_id}/meta.json", meta)
        cmd = AgentCommand(id=f"cmd_{uuid.uuid4().hex[:12]}", timestamp=datetime.now(timezone.utc),
                           type="start_run", payload={"run_id": run_id, "workflow_id": wid, "mode": mode})
        self._transport.send_command(cmd)
        return {"run_id": run_id, "mode": mode, "status": "started"}

    async def _fn_run_computer_use(self, goal):
        from shared.ipc_models import AgentCommand
        # Create a temporary workflow with just the goal as description
        workflow_id = f"wf_cu_{uuid.uuid4().hex[:8]}"
        wf = {"workflow_id": workflow_id, "name": goal[:50], "description": goal, "version": 1, "steps": []}
        await self._storage.write_json(f"workflows/{workflow_id}/latest.json", wf)
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        meta = {
            "run_id": run_id, "workflow_id": workflow_id, "workflow_name": goal[:50],
            "status": "pending", "started_at": datetime.now(timezone.utc).isoformat(),
            "current_step": 0, "total_steps": 0, "mode": "computer_use",
        }
        await self._storage.write_json(f"runs/{run_id}/meta.json", meta)
        cmd = AgentCommand(id=f"cmd_{uuid.uuid4().hex[:12]}", timestamp=datetime.now(timezone.utc),
                           type="start_run", payload={"run_id": run_id, "workflow_id": workflow_id, "mode": "computer_use"})
        self._transport.send_command(cmd)
        return {"run_id": run_id, "goal": goal, "status": "started"}

    async def _fn_start_recording(self, args):
        from shared.ipc_models import AgentCommand
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        cmd = AgentCommand(id=f"cmd_{uuid.uuid4().hex[:12]}", timestamp=datetime.now(timezone.utc),
                           type="start_recording", payload={"session_id": session_id, "purpose": args.get("purpose",""), "apps": args.get("apps",[])})
        self._transport.send_command(cmd)
        return {"session_id": session_id, "status": "recording_started"}

    async def _fn_stop_recording(self):
        from shared.ipc_models import AgentCommand
        cmd = AgentCommand(id=f"cmd_{uuid.uuid4().hex[:12]}", timestamp=datetime.now(timezone.utc), type="stop_recording", payload={})
        self._transport.send_command(cmd)
        return {"status": "recording_stopped"}

    async def _fn_get_run_result(self, run_id):
        meta = await self._storage.read_json(f"runs/{run_id}/meta.json")
        if not meta:
            return {"error": "실행 결과를 찾을 수 없습니다"}
        result = {"run_id": run_id, "status": meta.get("status"), "error": meta.get("error")}
        verification = await self._storage.read_json(f"runs/{run_id}/verification.json")
        if verification:
            result["verification"] = verification
        diagnosis = await self._storage.read_json(f"runs/{run_id}/diagnosis.json")
        if diagnosis:
            result["diagnosis"] = diagnosis
        return result

    async def _fn_analyze_failure(self, run_id):
        meta = await self._storage.read_json(f"runs/{run_id}/meta.json")
        if not meta:
            return {"error": "실행을 찾을 수 없습니다"}
        diagnosis = await self._storage.read_json(f"runs/{run_id}/diagnosis.json")
        if diagnosis:
            return {"run_id": run_id, "diagnosis": diagnosis}
        return {"run_id": run_id, "status": meta.get("status"), "error": meta.get("error"), "hint": "진단 리포트가 아직 생성되지 않았습니다"}

    # -- History management --

    async def _load_history(self, session_id):
        data = await self._storage.read_json(f"chat/{session_id}/history.json")
        if not data:
            return []
        # Reconstruct Content objects from saved data
        contents = []
        for item in data:
            parts = []
            for p in item.get("parts", []):
                if p.get("text"):
                    parts.append(types.Part.from_text(text=p["text"]))
                elif p.get("function_call"):
                    # Skip reconstructing function calls for simplicity
                    pass
            if parts:
                contents.append(types.Content(role=item.get("role","user"), parts=parts))
        return contents

    async def _save_history(self, session_id, history):
        # Serialize Content objects to JSON-safe format
        data = []
        for content in history:
            item = {"role": content.role, "parts": []}
            for part in content.parts:
                if part.text:
                    item["parts"].append({"text": part.text})
                elif part.function_call:
                    item["parts"].append({"function_call": {"name": part.function_call.name}})
                elif part.function_response:
                    item["parts"].append({"function_response": {"name": part.function_response.name}})
            data.append(item)
        # Keep only last 50 messages to prevent token overflow
        data = data[-50:]
        await self._storage.write_json(f"chat/{session_id}/history.json", data)

    async def get_history(self, session_id):
        data = await self._storage.read_json(f"chat/{session_id}/history.json")
        return data or []

    async def clear_history(self, session_id):
        await self._storage.write_json(f"chat/{session_id}/history.json", [])

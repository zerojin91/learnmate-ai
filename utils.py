"""
통합 유틸리티 모듈 - 토큰 관리 + LangGraph 스트리밍
"""
from typing import Any, Dict, List, Callable, Optional
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
import uuid
from config import Config


# =============================================================================
# 토큰 관리 유틸리티
# =============================================================================

def estimate_tokens(text: str) -> int:
    """
    텍스트의 토큰 수를 대략적으로 추정합니다.
    
    Args:
        text (str): 토큰 수를 계산할 텍스트
        
    Returns:
        int: 추정된 토큰 수
    """
    return len(text) // Config.AVERAGE_CHARS_PER_TOKEN


def calculate_conversation_tokens(conversation_history: List[Dict[str, str]]) -> int:
    """
    대화 기록의 총 토큰 수를 계산합니다.
    
    Args:
        conversation_history: 대화 기록 리스트
        
    Returns:
        int: 총 토큰 수
    """
    total_tokens = 0
    for message in conversation_history:
        total_tokens += estimate_tokens(message.get("content", ""))
    return total_tokens


def trim_conversation_history(conversation_history: List[Dict[str, str]], max_tokens: int) -> List[Dict[str, str]]:
    """
    대화 기록을 토큰 제한에 맞게 잘라냅니다.
    최신 메시지부터 유지하며, 토큰 제한을 초과하지 않도록 합니다.
    과거 기록부터 자동으로 삭제됩니다.
    
    Args:
        conversation_history: 전체 대화 기록
        max_tokens: 최대 토큰 수
        
    Returns:
        List[Dict[str, str]]: 토큰 제한에 맞는 대화 기록
    """
    if not conversation_history:
        return []
    
    original_count = len(conversation_history)
    
    # 최신 메시지부터 역순으로 확인
    trimmed_history = []
    current_tokens = 0
    
    for message in reversed(conversation_history):
        message_tokens = estimate_tokens(message.get("content", ""))
        
        # 토큰 제한을 초과하지 않는 경우에만 추가
        if current_tokens + message_tokens <= max_tokens:
            trimmed_history.insert(0, message)  # 앞쪽에 삽입하여 순서 유지
            current_tokens += message_tokens
        else:
            # 토큰 제한 초과시 더 이상 추가하지 않음 (과거 기록 삭제)
            break
    
    # 대화 기록이 잘렸는지 로그 출력
    if len(trimmed_history) < original_count:
        deleted_count = original_count - len(trimmed_history)
        print(f"🗑️  대화 기록 정리: {deleted_count}개 과거 메시지 삭제됨 (토큰 절약: {current_tokens}/{max_tokens})")
    
    return trimmed_history


def log_token_usage(conversation_history: List[Dict[str, str]]):
    """
    토큰 사용량을 로그로 출력합니다.
    """
    current_tokens = calculate_conversation_tokens(conversation_history)
    max_tokens = Config.get_effective_max_tokens()
    usage_percent = current_tokens/max_tokens*100
    
    print(f"📊 토큰 사용량: {current_tokens}/{max_tokens} ({usage_percent:.1f}%)")
    
    # 단계별 경고
    if usage_percent > 90:
        print("🚨 토큰 사용량 위험! 곧 과거 메시지가 삭제됩니다.")
    elif usage_percent > 80:
        print("⚠️  토큰 사용량이 높습니다. 대화 기록이 곧 정리될 예정입니다.")
    elif usage_percent > 60:
        print("📈 토큰 사용량이 증가하고 있습니다.")


def apply_chat_template(conversation_history: List[Dict[str, str]], modified_message: str, system_prompt: str) -> str:
    """
    HuggingFace 스타일 Chat Template으로 대화 기록을 하나의 프롬프트로 변환합니다.
    
    Args:
        conversation_history: 전체 대화 기록
        modified_message: 마지막 사용자 메시지 (툴 사용해 추가된)
        system_prompt: 시스템 프롬프트
        
    Returns:
        str: Chat Template 형식의 전체 프롬프트
    """
    template = ""
    
    # 시스템 메시지 추가
    template += f"<|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"
    
    # 대화 기록 처리
    for i, item in enumerate(conversation_history):
        role = item["role"]
        if role == "user":
            role = "user"
            # 마지막 사용자 메시지만 "(툴 사용해)" 추가
            content = modified_message if i == len(conversation_history) - 1 else item["content"]
        elif role == "assistant":
            role = "assistant"
            content = item["content"]
        else:
            continue
        
        template += f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>"
    
    # assistant 응답 시작 토큰 추가
    template += "<|start_header_id|>assistant<|end_header_id|>\n\n"
    
    return template


# =============================================================================
# LangGraph 스트리밍 유틸리티
# =============================================================================

def random_uuid():
    return str(uuid.uuid4())


async def astream_graph(
    graph: CompiledStateGraph,
    inputs: dict,
    config: Optional[RunnableConfig] = None,
    node_names: List[str] = [],
    callback: Optional[Callable] = None,
    stream_mode: str = "messages",
    include_subgraphs: bool = False,
) -> Dict[str, Any]:
    """
    LangGraph의 실행 결과를 비동기적으로 스트리밍하고 직접 출력하는 함수입니다.

    Args:
        graph (CompiledStateGraph): 실행할 컴파일된 LangGraph 객체
        inputs (dict): 그래프에 전달할 입력값 딕셔너리
        config (Optional[RunnableConfig]): 실행 설정 (선택적)
        node_names (List[str], optional): 출력할 노드 이름 목록. 기본값은 빈 리스트
        callback (Optional[Callable], optional): 각 청크 처리를 위한 콜백 함수. 기본값은 None
            콜백 함수는 {"node": str, "content": Any} 형태의 딕셔너리를 인자로 받습니다.
        stream_mode (str, optional): 스트리밍 모드 ("messages" 또는 "updates"). 기본값은 "messages"
        include_subgraphs (bool, optional): 서브그래프 포함 여부. 기본값은 False

    Returns:
        Dict[str, Any]: 최종 결과 (선택적)
    """
    config = config or {}
    final_result = {}

    def format_namespace(namespace):
        return namespace[-1].split(":")[0] if len(namespace) > 0 else "root graph"

    prev_node = ""

    if stream_mode == "messages":
        async for chunk_msg, metadata in graph.astream(
            inputs, config, stream_mode=stream_mode
        ):
            curr_node = metadata["langgraph_node"]
            final_result = {
                "node": curr_node,
                "content": chunk_msg,
                "metadata": metadata,
            }

            # node_names가 비어있거나 현재 노드가 node_names에 있는 경우에만 처리
            if not node_names or curr_node in node_names:
                # 콜백 함수가 있는 경우 실행
                if callback:
                    result = callback({"node": curr_node, "content": chunk_msg})
                    if hasattr(result, "__await__"):
                        await result
                # 콜백이 없는 경우 기본 출력
                else:
                    # 노드가 변경된 경우에만 구분선 출력
                    if curr_node != prev_node:
                        print("\n" + "=" * 50)
                        print(f"🔄 Node: \033[1;36m{curr_node}\033[0m 🔄")
                        print("- " * 25)

                    # Claude/Anthropic 모델의 토큰 청크 처리 - 항상 텍스트만 추출
                    if hasattr(chunk_msg, "content"):
                        # 리스트 형태의 content (Anthropic/Claude 스타일)
                        if isinstance(chunk_msg.content, list):
                            for item in chunk_msg.content:
                                if isinstance(item, dict) and "text" in item:
                                    print(item["text"], end="", flush=True)
                        # 문자열 형태의 content
                        elif isinstance(chunk_msg.content, str):
                            print(chunk_msg.content, end="", flush=True)
                    # 그 외 형태의 chunk_msg 처리
                    else:
                        print(chunk_msg, end="", flush=True)

                prev_node = curr_node

    elif stream_mode == "updates":
        # 에러 수정: 언패킹 방식 변경
        # REACT 에이전트 등 일부 그래프에서는 단일 딕셔너리만 반환함
        async for chunk in graph.astream(
            inputs, config, stream_mode=stream_mode, subgraphs=include_subgraphs
        ):
            # 반환 형식에 따라 처리 방법 분기
            if isinstance(chunk, tuple) and len(chunk) == 2:
                # 기존 예상 형식: (namespace, chunk_dict)
                namespace, node_chunks = chunk
            else:
                # 단일 딕셔너리만 반환하는 경우 (REACT 에이전트 등)
                namespace = []  # 빈 네임스페이스 (루트 그래프)
                node_chunks = chunk  # chunk 자체가 노드 청크 딕셔너리

            # 딕셔너리인지 확인하고 항목 처리
            if isinstance(node_chunks, dict):
                for node_name, node_chunk in node_chunks.items():
                    final_result = {
                        "node": node_name,
                        "content": node_chunk,
                        "namespace": namespace,
                    }

                    # node_names가 비어있지 않은 경우에만 필터링
                    if len(node_names) > 0 and node_name not in node_names:
                        continue

                    # 콜백 함수가 있는 경우 실행
                    if callback is not None:
                        result = callback({"node": node_name, "content": node_chunk})
                        if hasattr(result, "__await__"):
                            await result
                    # 콜백이 없는 경우 기본 출력
                    else:
                        # 노드가 변경된 경우에만 구분선 출력 (messages 모드와 동일하게)
                        if node_name != prev_node:
                            print("\n" + "=" * 50)
                            print(f"🔄 Node: \033[1;36m{node_name}\033[0m 🔄")
                            print("- " * 25)

                        # 노드의 청크 데이터 출력 - 텍스트 중심으로 처리
                        if isinstance(node_chunk, dict):
                            for k, v in node_chunk.items():
                                if isinstance(v, BaseMessage):
                                    # BaseMessage의 content 속성이 텍스트나 리스트인 경우를 처리
                                    if hasattr(v, "content"):
                                        if isinstance(v.content, list):
                                            for item in v.content:
                                                if (
                                                    isinstance(item, dict)
                                                    and "text" in item
                                                ):
                                                    print(
                                                        item["text"], end="", flush=True
                                                    )
                                        else:
                                            print(v.content, end="", flush=True)
                                    else:
                                        v.pretty_print()
                                elif isinstance(v, list):
                                    for list_item in v:
                                        if isinstance(list_item, BaseMessage):
                                            if hasattr(list_item, "content"):
                                                if isinstance(list_item.content, list):
                                                    for item in list_item.content:
                                                        if (
                                                            isinstance(item, dict)
                                                            and "text" in item
                                                        ):
                                                            print(
                                                                item["text"],
                                                                end="",
                                                                flush=True,
                                                            )
                                                else:
                                                    print(
                                                        list_item.content,
                                                        end="",
                                                        flush=True,
                                                    )
                                            else:
                                                list_item.pretty_print()
                                        elif (
                                            isinstance(list_item, dict)
                                            and "text" in list_item
                                        ):
                                            print(list_item["text"], end="", flush=True)
                                        else:
                                            print(list_item, end="", flush=True)
                                elif isinstance(v, dict) and "text" in v:
                                    print(v["text"], end="", flush=True)
                                else:
                                    print(v, end="", flush=True)
                        elif node_chunk is not None:
                            if hasattr(node_chunk, "__iter__") and not isinstance(
                                node_chunk, str
                            ):
                                for item in node_chunk:
                                    if isinstance(item, dict) and "text" in item:
                                        print(item["text"], end="", flush=True)
                                    else:
                                        print(item, end="", flush=True)
                            else:
                                print(node_chunk, end="", flush=True)

                        # 구분선을 여기서 출력하지 않음 (messages 모드와 동일하게)

                    prev_node = node_name
            else:
                # 딕셔너리가 아닌 경우 전체 청크 출력
                print("\n" + "=" * 50)
                print(f"🔄 Raw output 🔄")
                print("- " * 25)
                print(node_chunks, end="", flush=True)
                # 구분선을 여기서 출력하지 않음
                final_result = {"content": node_chunks}

    else:
        raise ValueError(
            f"Invalid stream_mode: {stream_mode}. Must be 'messages' or 'updates'."
        )

    # 필요에 따라 최종 결과 반환
    return final_result

async def ainvoke_graph(
    graph: CompiledStateGraph,
    inputs: dict,
    config: Optional[RunnableConfig] = None,
    node_names: List[str] = [],
    callback: Optional[Callable] = None,
    include_subgraphs: bool = True,
) -> Dict[str, Any]:
    """
    LangGraph 앱의 실행 결과를 비동기적으로 스트리밍하여 출력하는 함수입니다.

    Args:
        graph (CompiledStateGraph): 실행할 컴파일된 LangGraph 객체
        inputs (dict): 그래프에 전달할 입력값 딕셔너리
        config (Optional[RunnableConfig]): 실행 설정 (선택적)
        node_names (List[str], optional): 출력할 노드 이름 목록. 기본값은 빈 리스트
        callback (Optional[Callable], optional): 각 청크 처리를 위한 콜백 함수. 기본값은 None
            콜백 함수는 {"node": str, "content": Any} 형태의 딕셔너리를 인자로 받습니다.
        include_subgraphs (bool, optional): 서브그래프 포함 여부. 기본값은 True

    Returns:
        Dict[str, Any]: 최종 결과 (마지막 노드의 출력)
    """
    config = config or {}
    final_result = {}

    def format_namespace(namespace):
        return namespace[-1].split(":")[0] if len(namespace) > 0 else "root graph"

    # subgraphs 매개변수를 통해 서브그래프의 출력도 포함
    async for chunk in graph.astream(
        inputs, config, stream_mode="updates", subgraphs=include_subgraphs
    ):
        # 반환 형식에 따라 처리 방법 분기
        if isinstance(chunk, tuple) and len(chunk) == 2:
            # 기존 예상 형식: (namespace, chunk_dict)
            namespace, node_chunks = chunk
        else:
            # 단일 딕셔너리만 반환하는 경우 (REACT 에이전트 등)
            namespace = []  # 빈 네임스페이스 (루트 그래프)
            node_chunks = chunk  # chunk 자체가 노드 청크 딕셔너리

        # 딕셔너리인지 확인하고 항목 처리
        if isinstance(node_chunks, dict):
            for node_name, node_chunk in node_chunks.items():
                final_result = {
                    "node": node_name,
                    "content": node_chunk,
                    "namespace": namespace,
                }

                # node_names가 비어있지 않은 경우에만 필터링
                if node_names and node_name not in node_names:
                    continue

                # 콜백 함수가 있는 경우 실행
                if callback is not None:
                    result = callback({"node": node_name, "content": node_chunk})
                    # 코루틴인 경우 await
                    if hasattr(result, "__await__"):
                        await result
                # 콜백이 없는 경우 기본 출력
                else:
                    print("\n" + "=" * 50)
                    formatted_namespace = format_namespace(namespace)
                    if formatted_namespace == "root graph":
                        print(f"🔄 Node: \033[1;36m{node_name}\033[0m 🔄")
                    else:
                        print(
                            f"🔄 Node: \033[1;36m{node_name}\033[0m in [\033[1;33m{formatted_namespace}\033[0m] 🔄"
                        )
                    print("- " * 25)

                    # 노드의 청크 데이터 출력
                    if isinstance(node_chunk, dict):
                        for k, v in node_chunk.items():
                            if isinstance(v, BaseMessage):
                                v.pretty_print()
                            elif isinstance(v, list):
                                for list_item in v:
                                    if isinstance(list_item, BaseMessage):
                                        list_item.pretty_print()
                                    else:
                                        print(list_item)
                            elif isinstance(v, dict):
                                for node_chunk_key, node_chunk_value in v.items():
                                    print(f"{node_chunk_key}:\n{node_chunk_value}")
                            else:
                                print(f"\033[1;32m{k}\033[0m:\n{v}")
                    elif node_chunk is not None:
                        if hasattr(node_chunk, "__iter__") and not isinstance(
                            node_chunk, str
                        ):
                            for item in node_chunk:
                                print(item)
                        else:
                            print(node_chunk)
                    print("=" * 50)
        else:
            # 딕셔너리가 아닌 경우 전체 청크 출력
            print("\n" + "=" * 50)
            print(f"🔄 Raw output 🔄")
            print("- " * 25)
            print(node_chunks)
            print("=" * 50)
            final_result = {"content": node_chunks}

    # 최종 결과 반환
    return final_result

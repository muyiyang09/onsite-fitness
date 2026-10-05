package com.onsitefitness.websocket;

import jakarta.websocket.OnClose;
import jakarta.websocket.OnMessage;
import jakarta.websocket.OnOpen;
import jakarta.websocket.Session;
import jakarta.websocket.server.PathParam;
import jakarta.websocket.server.ServerEndpoint;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * WebSocket服务
 *
 * <p>并发安全（§6.11）：HTTP 线程（下单/催单触发推送）与定时线程（WebSocketTask 每 5s 心跳）
 * 会并发对同一 Session 调 {@code getBasicRemote().sendText()}，HashMap 并发写有风险，
 * 故用 {@link ConcurrentHashMap} 存会话，发送时逐 session 加锁防两线程并发写同一连接帧。
 *
 * <p><b>升级触发条件</b>：后端扩到 2+ 副本时，才需要引入 Redis Pub/Sub 跨实例广播——
 * 当前 docker-compose 后端是固定 container_name 单副本，无此需求；且本类由 WS 容器实例化
 * 而非 Spring 管理，静态注入模板类易错、收益为零，故暂不做。
 */
@Component
@ServerEndpoint("/ws/{sid}")
@Slf4j
public class WebSocketServer {

    //存放会话对象（并发容器：多线程并发 put/remove/迭代安全）
    private static final Map<String, Session> sessionMap = new ConcurrentHashMap<>();

    /**
     * 连接建立成功调用的方法
     */
    @OnOpen
    public void onOpen(Session session, @PathParam("sid") String sid) {
        log.info("客户端：{} 建立连接", sid);
        sessionMap.put(sid, session);
    }

    /**
     * 收到客户端消息后调用的方法
     *
     * @param message 客户端发送过来的消息
     */
    @OnMessage
    public void onMessage(String message, @PathParam("sid") String sid) {
        log.info("收到来自客户端：{} 的信息:{}", sid, message);
    }

    /**
     * 连接关闭调用的方法
     *
     * @param sid
     */
    @OnClose
    public void onClose(@PathParam("sid") String sid) {
        log.info("连接断开:{}", sid);
        sessionMap.remove(sid);
    }

    /**
     * 群发
     *
     * @param message
     */
    public void sendToAllClient(String message) {
        sessionMap.values().forEach(session -> {
            try {
                synchronized (session) {                 // 防止两线程并发向同一连接写帧
                    if (session.isOpen()) {
                        session.getBasicRemote().sendText(message);
                    }
                }
            } catch (Exception e) {
                log.warn("WebSocket 推送失败：{}", e.getMessage());
            }
        });
    }

}

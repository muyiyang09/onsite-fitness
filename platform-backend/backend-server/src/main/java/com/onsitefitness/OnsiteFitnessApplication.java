package com.onsitefitness;

import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.core.env.Environment;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.transaction.annotation.EnableTransactionManagement;

@SpringBootApplication
@EnableTransactionManagement //开启注解方式的事务管理
@Slf4j
@EnableCaching //开启缓存
@EnableScheduling //开启定时任务（派单池超时兜底）
@EnableAsync //开启异步（评价摘要、AI 调用等降级异步刷新）
public class OnsiteFitnessApplication {
    public static void main(String[] args) {
        // §13.7：裸启动（无显式 --spring.profiles.active）时若回退到 dev 配置，
        // 打 WARN 日志提醒——dev 含 mockLogin 放行等开发态开关，生产误启动有安全风险。
        ConfigurableApplicationContext ctx = SpringApplication.run(OnsiteFitnessApplication.class, args);
        Environment env = ctx.getEnvironment();
        String[] activeProfiles = env.getActiveProfiles();
        if (activeProfiles.length == 0 || java.util.Arrays.asList(activeProfiles).contains("dev")) {
            log.warn("⚠️ 当前激活 profile 包含 dev 或未显式指定——生产环境请用 --spring.profiles.active=docker/prod 启动");
        }
        log.info("server started");
    }
}

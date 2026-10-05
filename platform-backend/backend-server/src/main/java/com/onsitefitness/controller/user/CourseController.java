package com.onsitefitness.controller.user;

import com.onsitefitness.result.Result;
import com.onsitefitness.service.CourseService;
import com.onsitefitness.vo.CourseVO;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.concurrent.TimeUnit;

@RestController("userCourseController")
@RequestMapping("/user/course")
@Slf4j
@Tag(name = "C端-课程浏览接口")
public class CourseController {
    @Autowired
    private RedisTemplate<Object, Object> redisTemplate;
    @Autowired
    private CourseService courseService;

    /**
     * 根据分类id查询课程
     * <p>
     * 缓存策略：<br>
     * • Redis 可用 → 读缓存，未命中则查 DB 并回写（60 分钟 TTL，避免脏缓存永久存在）<br>
     * • Redis 不可用（本机未安装/连不上）→ 降级为直查 DB，保证页面可用，仅打印 WARN 日志
     * </p>
     */
    @GetMapping("/list")
    @Operation(summary = "根据分类id查询课程")
    public Result<List<CourseVO>> list(Long categoryId) {
        final String key = "course_" + categoryId;

        // ---------- 阶段1: 尝试读缓存（失败就降级） ----------
        List<CourseVO> list = null;
        boolean redisOk = false;
        try {
            Object cached = redisTemplate.opsForValue().get(key);
            if (cached instanceof List) {
                @SuppressWarnings("unchecked")
                List<CourseVO> casted = (List<CourseVO>) cached;
                if (casted.size() > 0) {
                    log.debug("课程分类{}命中缓存,条数={}", categoryId, casted.size());
                    return Result.success(casted);
                }
            }
            redisOk = true;
        } catch (Exception e) {
            log.warn("课程列表读缓存失败(降级直查DB) categoryId={} msg={}", categoryId, e.getMessage());
        }

        // ---------- 阶段2: 查 DB ----------
        list = courseService.list(categoryId);

        // ---------- 阶段3: 尝试写缓存（失败也不影响返回） ----------
        if (redisOk && list != null) {
            try {
                redisTemplate.opsForValue().set(key, list, 60, TimeUnit.MINUTES);
            } catch (Exception e) {
                log.warn("课程列表写缓存失败 categoryId={} msg={}", categoryId, e.getMessage());
            }
        }
        return Result.success(list);
    }
}

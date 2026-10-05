package com.onsitefitness.controller.admin;

import com.onsitefitness.dto.CourseDTO;
import com.onsitefitness.dto.CoursePageQueryDTO;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.result.Result;
import com.onsitefitness.service.CourseService;
import com.onsitefitness.vo.CourseVO;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Set;

@RestController
@RequestMapping("/admin/course")
@Slf4j
@Tag(name = "课程相关接口")
public class CourseController {
    @Autowired
    private RedisTemplate redisTemplate;
    @Autowired
    private CourseService courseService;

    /**
     * 新增课程
     */
    @PostMapping
    @Operation(summary = "新增课程")
    public Result save(@RequestBody CourseDTO courseDTO) {
        log.info("新增课程：{}", courseDTO);
        courseService.save(courseDTO);
        //清理缓存数据
        String key = "course_" + courseDTO.getCategoryId();
        cleanCache(key);
        return Result.success();
    }

    /**
     * 课程分页查询
     */
    @GetMapping("/page")
    @Operation(summary = "课程分页查询")
    public Result<PageResult> page(CoursePageQueryDTO coursePageQueryDTO) {
        log.info("课程分页查询：{}", coursePageQueryDTO);
        PageResult pageResult = courseService.pageQuery(coursePageQueryDTO);
        return Result.success(pageResult);
    }

    /**
     * 批量删除课程
     */
    @DeleteMapping
    @Operation(summary = "课程批量删除")
    public Result delete(@RequestParam List<Long> ids) {
        log.info("课程批量删除：{}", ids);
        courseService.deleteBatch(ids);
        //清理缓存数据，将所有课程缓存数据清理掉
        cleanCache("course_*");
        return Result.success();
    }

    /**
     * 根据ID查询课程
     */
    @GetMapping("/{id}")
    @Operation(summary = "根据id查询课程")
    public Result<CourseVO> getById(@PathVariable Long id) {
        log.info("根据ID查询课程：{}", id);
        CourseVO courseVO = courseService.getById(id);
        return Result.success(courseVO);
    }

    /**
     * 修改课程
     */
    @PutMapping
    @Operation(summary = "修改课程")
    public Result update(@RequestBody CourseDTO courseDTO) {
        log.info("修改课程：{}", courseDTO);
        courseService.update(courseDTO);
        //清理缓存数据，如果修改分类可能会影响两类数据缓存
        cleanCache("course_*");
        return Result.success();
    }

    /**
     * 课程起售停售
     * @param status
     * @param id
     * @return
     */
    @PostMapping("/status/{status}")
    @Operation(summary = "课程起售停售")
    public Result<String> startOrStop(@PathVariable Integer status, Long id) {
        log.info("课程起售停售：{}", status);
        courseService.startOrStop(status, id);
        //清理缓存数据，如果修改状态可能会影响两类数据缓存
        cleanCache("course_*");
        return Result.success();
    }

    /**
     * 根据分类id查询课程
     * @param categoryId
     * @return
     */
    @GetMapping("/list")
    @Operation(summary = "根据分类id查询课程")
    public Result<List<CourseVO>> list(Long categoryId) {
        List<CourseVO> list = courseService.list(categoryId);
        return Result.success(list);
    }

    /**
     * 清理缓存数据
     */
    private void cleanCache(String pattern) {
        Set keys = redisTemplate.keys(pattern);
        redisTemplate.delete(keys);
    }
}

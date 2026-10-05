package com.onsitefitness.controller.admin;

import com.onsitefitness.dto.CoursePackageDTO;
import com.onsitefitness.dto.CoursePackagePageQueryDTO;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.result.Result;
import com.onsitefitness.service.CoursePackageService;
import com.onsitefitness.vo.CoursePackageVO;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/admin/course_package")
@Tag(name = "训练套餐相关接口")
@Slf4j
public class CoursePackageController {

    @Autowired
    private CoursePackageService coursePackageService;

    /**
     * 新增套餐
     * @param coursePackageDTO
     * @return
     */
    @PostMapping
    @Operation(summary = "新增套餐")
    @CacheEvict(cacheNames = "coursePackageCache", key = "#coursePackageDTO.categoryId")
    public Result save(@RequestBody CoursePackageDTO coursePackageDTO) {
        log.info("新增套餐：{}", coursePackageDTO);
        coursePackageService.save(coursePackageDTO);
        return Result.success();
    }

    /**
     * 分页查询
     * @param coursePackagePageQueryDTO
     * @return
     */
    @GetMapping("/page")
    @Operation(summary = "分页查询")
    public Result<PageResult> page(CoursePackagePageQueryDTO coursePackagePageQueryDTO) {
        log.info("套餐分页查询：{}", coursePackagePageQueryDTO);
        PageResult pageResult = coursePackageService.pageQuery(coursePackagePageQueryDTO);
        return Result.success(pageResult);
    }

    /**
     * 批量删除套餐
     * @param ids
     * @return
     */
    @DeleteMapping
    @Operation(summary = "批量删除套餐")
    @CacheEvict(cacheNames = "coursePackageCache", allEntries = true)
    public Result delete(@RequestParam List<Long> ids) {
        log.info("批量删除套餐：{}", ids);
        coursePackageService.deleteBatch(ids);
        return Result.success();
    }

    /**
     * 根据id查询套餐，用于修改页面回显数据
     *
     * @param id
     * @return
     */
    @GetMapping("/{id}")
    @Operation(summary = "根据id查询套餐")
    public Result<CoursePackageVO> getById(@PathVariable Long id) {
        log.info("根据id查询套餐：{}", id);
        CoursePackageVO coursePackageVO = coursePackageService.getById(id);
        return Result.success(coursePackageVO);
    }

    /**
     * 修改套餐
     *
     * @param coursePackageDTO
     * @return
     */
    @PutMapping
    @Operation(summary = "修改套餐")
    @CacheEvict(cacheNames = "coursePackageCache", allEntries = true)
    public Result update(@RequestBody CoursePackageDTO coursePackageDTO) {
        log.info("修改套餐：{}", coursePackageDTO);
        coursePackageService.update(coursePackageDTO);
        return Result.success();
    }

    /**
     * 套餐起售停售
     * @param status
     * @param id
     * @return
     */
    @PostMapping("/status/{status}")
    @Operation(summary = "套餐起售停售")
    @CacheEvict(cacheNames = "coursePackageCache", allEntries = true)
    public Result startOrStop(@PathVariable Integer status, Long id) {
        log.info("套餐起售停售：{}", status);
        coursePackageService.startOrStop(status, id);
        return Result.success();
    }

    /**
     * 根据分类id查询套餐
     * @param categoryId
     * @return
     */
    @GetMapping("/list")
    @Operation(summary = "根据分类id查询套餐")
    public Result<List<com.onsitefitness.entity.CoursePackage>> list(Long categoryId) {
        List<com.onsitefitness.entity.CoursePackage> list = coursePackageService.list(categoryId);
        return Result.success(list);
    }
}

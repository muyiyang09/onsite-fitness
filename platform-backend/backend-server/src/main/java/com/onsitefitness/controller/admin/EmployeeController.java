package com.onsitefitness.controller.admin;

import com.onsitefitness.constant.JwtClaimsConstant;
import com.onsitefitness.dto.EmployeeDTO;
import com.onsitefitness.dto.EmployeeLoginDTO;
import com.onsitefitness.dto.EmployeePageQueryDTO;
import com.onsitefitness.dto.PasswordEditDTO;
import com.onsitefitness.entity.Employee;
import com.onsitefitness.properties.JwtProperties;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.result.Result;
import com.onsitefitness.service.EmployeeService;
import com.onsitefitness.service.TokenBlacklistService;
import com.onsitefitness.utils.JwtUtil;
import com.onsitefitness.vo.EmployeeLoginVO;
import io.jsonwebtoken.Claims;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

/**
 * 员工管理
 */
@RestController
@RequestMapping("/admin/employee")
@Tag(name = "员工相关接口")
@Slf4j
public class EmployeeController {

    @Autowired
    private EmployeeService employeeService;
    @Autowired
    private JwtProperties jwtProperties;
    @Autowired
    private TokenBlacklistService tokenBlacklistService;

    /**
     * 登录
     *
     * @param employeeLoginDTO
     * @return
     */
    @PostMapping("/login")
    public Result<EmployeeLoginVO> login(@RequestBody EmployeeLoginDTO employeeLoginDTO) {
        log.info("员工登录：{}", employeeLoginDTO.getUsername());

        Employee employee = employeeService.login(employeeLoginDTO);

        //登录成功后，生成jwt令牌
        Map<String, Object> claims = new HashMap<>();
        claims.put(JwtClaimsConstant.EMP_ID, employee.getId());
        claims.put(JwtClaimsConstant.ROLE, employee.getRole() == null ? "dev" : employee.getRole());
        JwtUtil.JwtTokenResult tokenResult = JwtUtil.createJWT(
                jwtProperties.getAdminSecretKey(),
                jwtProperties.getAdminTtl(),
                claims);

        tokenBlacklistService.registerUserToken(
                String.valueOf(employee.getId()),
                tokenResult.getJti(),
                jwtProperties.getAdminTtl());

        EmployeeLoginVO employeeLoginVO = EmployeeLoginVO.builder()
                .id(employee.getId())
                .userName(employee.getUsername())
                .name(employee.getName())
                .token(tokenResult.getToken())
                .build();

        return Result.success(employeeLoginVO);
    }

    /**
     * 退出
     *
     * @return
     */
    @PostMapping("/logout")
    public Result<String> logout(HttpServletRequest request) {
        String token = request.getHeader(jwtProperties.getAdminTokenName());
        if (token != null) {
            try {
                Claims claims = JwtUtil.parseJWT(
                        jwtProperties.getAdminSecretKey(), token);
                String jti = claims.get(JwtClaimsConstant.JTI) != null
                        ? claims.get(JwtClaimsConstant.JTI).toString()
                        : null;
                if (jti != null) {
                    tokenBlacklistService.blacklist(jti, jwtProperties.getAdminTtl());
                }
            } catch (Exception ignored) {
            }
        }
        return Result.success();
    }

    /**
     * 新增员工
     */
    @PostMapping
    @Operation(summary = "新增员工")  //  添加swagger注解
    public Result save(@RequestBody EmployeeDTO employeeDTO){
        log.info("新增员工：{}", employeeDTO);
        employeeService.save(employeeDTO);
        return Result.success();
    }

    /**
     * 分页查询
     */
    @GetMapping("/page")
    @Operation(summary = "员工分页查询")  //  添加swagger注解
     public Result<PageResult> Page(EmployeePageQueryDTO employeePageQueryDTO){
        log.info("分页查询：{}", employeePageQueryDTO);
        PageResult result = employeeService.pageQuery(employeePageQueryDTO);
        return Result.success(result);
    }
    /**
     * 启用禁用员工账号
     */
    @PostMapping("/status/{status}")
    @Operation(summary = "启用禁用员工账号")  //  添加swagger注解
    public Result<String> status(@PathVariable("status") Integer status, @RequestBody Long id){
        log.info("启用禁用员工账号：{}, {}", status, id);
        employeeService.startOrStop(status, id);
        return Result.success();
    }
    /**
     * 根据id查询员工信息
     */
    @GetMapping("/{id}")
    @Operation(summary = "根据id查询员工信息")  //  添加swagger注解
    public Result<Employee> get(@PathVariable("id") Long id){
        log.info("根据id查询员工信息：{}", id);
        Employee employee = employeeService.getById(id);
        return Result.success(employee);
    }
    /**
     * 更新员工信息
     */
    @PutMapping
    @Operation(summary = "更新员工信息")  //  添加swagger注解
    public Result update(@RequestBody EmployeeDTO employeeDTO){
        log.info("更新员工信息：{}", employeeDTO);
        employeeService.update(employeeDTO);
        return Result.success();
    }

    /**
     * 员工修改密码
     * @param employeeDTO
     * @return
     */
    @PutMapping("/editPassword")
    @Operation(summary = "员工修改密码")  //  添加swagger注解
    public Result updatePassword(@RequestBody PasswordEditDTO passwordEditDTO){
        log.info("员工修改密码：{}", passwordEditDTO);
        employeeService.editPassword(passwordEditDTO);
        return Result.success();
    }


}

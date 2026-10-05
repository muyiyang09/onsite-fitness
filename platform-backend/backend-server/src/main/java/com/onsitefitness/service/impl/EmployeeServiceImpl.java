package com.onsitefitness.service.impl;

import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import com.onsitefitness.constant.MessageConstant;
import com.onsitefitness.constant.PasswordConstant;
import com.onsitefitness.constant.StatusConstant;
import com.onsitefitness.context.BaseContext;
import com.onsitefitness.dto.EmployeeDTO;
import com.onsitefitness.dto.EmployeeLoginDTO;
import com.onsitefitness.dto.EmployeePageQueryDTO;
import com.onsitefitness.dto.PasswordEditDTO;
import com.onsitefitness.entity.Employee;
import com.onsitefitness.exception.AccountLockedException;
import com.onsitefitness.exception.AccountNotFoundException;
import com.onsitefitness.exception.PasswordEditFailedException;
import com.onsitefitness.exception.PasswordErrorException;
import com.onsitefitness.mapper.EmployeeMapper;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.service.EmployeeService;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service
public class EmployeeServiceImpl implements EmployeeService {

    @Autowired
    private EmployeeMapper employeeMapper;

    /** 密码哈希：BCrypt（无盐 MD5 已弃用，见 §5.5 安全审查） */
    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

    /**
     * 员工登录
     *
     * @param employeeLoginDTO
     * @return
     */
    public Employee login(EmployeeLoginDTO employeeLoginDTO) {
        String username = employeeLoginDTO.getUsername();
        String password = employeeLoginDTO.getPassword();

        //1、根据用户名查询数据库中的数据
        Employee employee = employeeMapper.getByUsername(username);

        //2、处理各种异常情况（用户名不存在、密码不对、账号被锁定）
        if (employee == null) {
            //账号不存在
            throw new AccountNotFoundException(MessageConstant.ACCOUNT_NOT_FOUND);
        }

        //密码比对（BCrypt matches：库中存哈希，输入原始密码比对）
        if (!passwordEncoder.matches(password, employee.getPassword())) {
            //密码错误
            throw new PasswordErrorException(MessageConstant.PASSWORD_ERROR);
        }

        if (employee.getStatus() == StatusConstant.DISABLE) {
            //账号被锁定
            throw new AccountLockedException(MessageConstant.ACCOUNT_LOCKED);
        }

        //3、返回实体对象
        return employee;
    }

    @Override
    public void save(EmployeeDTO employeeDTO) {
        // TODO 保存员工信息
        Employee employee = new Employee();
        BeanUtils.copyProperties(employeeDTO, employee);  //   把dto对象中的属性复制到实体对象中
        employee.setStatus(StatusConstant.ENABLE);   //   设置默认状态为启用
        employee.setPassword(passwordEncoder.encode(PasswordConstant.DEFAULT_PASSWORD)); //   设置默认密码(BCrypt)
        //公共属性不需要设置,aop 会自动填充
//        employee.setUpdateTime(LocalDateTime.now());
//        employee.setCreateTime(LocalDateTime.now());
//
//        employee.setCreateUser(BaseContext.getCurrentId());  //  获取当前登录用户id
//        employee.setUpdateUser(BaseContext.getCurrentId());  //  获取当前登录用户id

        employeeMapper.insert(employee);     //   插入员工信息
    }

    @Override
    public PageResult pageQuery(EmployeePageQueryDTO employeePageQueryDTO) {
        // TODO 查询员工信息
        PageHelper.startPage(employeePageQueryDTO.getPage(), employeePageQueryDTO.getPageSize());//  开始分页 查询
        Page<Employee> page = employeeMapper.pageQuery(employeePageQueryDTO);

        long total = page.getTotal();
        List<Employee> records = page.getResult();
        return new PageResult(total, records);
    }

    /**
     * 启用或禁用员工
     * @param status
     * @param id
     */
    @Override
    public void startOrStop(Integer status, Long id) {
        // update employee set status = #{status} where id = #{id}
//        Employee employee = new Employee();
        Employee employee = Employee.builder().status(status).id(id).build();
        employeeMapper.update(employee);


    }

    @Override
    public Employee getById(Long id) {
        Employee employee = employeeMapper.selectByPrimaryKey(id);
        employee.setPassword("****");  //   密码不返回
        return employee;
    }

    @Override
    public void update(EmployeeDTO employeeDTO) {
        Employee employee = new Employee();
        BeanUtils.copyProperties(employeeDTO, employee);

//        employee.setUpdateTime(LocalDateTime.now());
//        employee.setUpdateUser(BaseContext.getCurrentId()); //  获取当前登录用户id
        employeeMapper.update(employee);
    }

    @Override
    public void editPassword(PasswordEditDTO passwordEditDTO) {
        // TODO 修改密码
        // 1.新旧密码重复抛出异常
        if(passwordEditDTO.getNewPassword().equals(passwordEditDTO.getOldPassword())){
            throw new PasswordEditFailedException(MessageConstant.PASSWORD_REPEAT);
        }
        // H获取当前用户的id
        Long empId = BaseContext.getCurrentId();
        // 3.根据id查询原始密码
        Employee employee = employeeMapper.selectByPrimaryKey(empId);
        // 4.校验旧密码（BCrypt matches 原始输入 vs 库中哈希）
        if (!passwordEncoder.matches(passwordEditDTO.getOldPassword(), employee.getPassword())) {
            throw new PasswordErrorException(MessageConstant.OLDPASSWORD_ERROR);
        }
        // 5.新密码 BCrypt 编码；oldPassword 传库中哈希作为 update 的 where 条件
        passwordEditDTO.setNewPassword(passwordEncoder.encode(passwordEditDTO.getNewPassword()));
        passwordEditDTO.setOldPassword(employee.getPassword());
        passwordEditDTO.setEmpId(empId);
        employeeMapper.updatePassword(passwordEditDTO);
    }

}

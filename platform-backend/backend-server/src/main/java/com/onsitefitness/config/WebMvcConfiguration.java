package com.onsitefitness.config;

import com.onsitefitness.interceptor.JwtTokenAdminInterceptor;
import com.onsitefitness.interceptor.JwtTokenCoachInterceptor;
import com.onsitefitness.interceptor.JwtTokenUserInterceptor;
import com.onsitefitness.interceptor.RateLimitInterceptor;
import com.onsitefitness.json.JacksonObjectMapper;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import lombok.extern.slf4j.Slf4j;
import org.springdoc.core.models.GroupedOpenApi;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.converter.HttpMessageConverter;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;

/**
 * 配置类，注册web层相关组件
 */
@Configuration
@Slf4j
public class WebMvcConfiguration implements WebMvcConfigurer {

    @Autowired
    private RateLimitInterceptor rateLimitInterceptor;
    @Autowired
    private JwtTokenAdminInterceptor jwtTokenAdminInterceptor;
    @Autowired
    private JwtTokenUserInterceptor jwtTokenUserInterceptor;
    @Autowired
    private JwtTokenCoachInterceptor jwtTokenCoachInterceptor;

    /**
     * 注册自定义拦截器
     *
     * @param registry
     */
    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        log.info("开始注册自定义拦截器...");

        // 限流拦截器 - 在 JWT 拦截器之后运行，排除健康检查、支付回调等路径
        registry.addInterceptor(rateLimitInterceptor)
                .addPathPatterns("/**")
                .excludePathPatterns("/actuator/**")
                .excludePathPatterns("/notify/**")
                .excludePathPatterns("/upload/**")
                .excludePathPatterns("/error")
                .excludePathPatterns("/swagger-ui/**")
                .excludePathPatterns("/v3/api-docs/**")
                .order(10);

        registry.addInterceptor(jwtTokenAdminInterceptor)
                .addPathPatterns("/admin/**")
                .excludePathPatterns("/admin/employee/login");

        registry.addInterceptor(jwtTokenUserInterceptor)
                .addPathPatterns("/user/**")
                // === 登录相关（无需鉴权） ===
                .excludePathPatterns("/user/user/login")
                .excludePathPatterns("/user/user/mockLogin")
                // === 店铺/运营状态 ===
                .excludePathPatterns("/user/shop/status")
                // === 浏览类公开接口（未登录用户也能看课程/教练/分类/套餐） ===
                //   注意: Spring 拦截器 excludePathPatterns 只支持 Ant 通配符(* ** ?)，不能写 {id} 占位符
                .excludePathPatterns("/user/category/list")
                .excludePathPatterns("/user/course/list")
                .excludePathPatterns("/user/course_package/**")
                .excludePathPatterns("/user/coach/list")
                .excludePathPatterns("/user/coach/*")        // 教练详情 GET /user/coach/{id}
                .excludePathPatterns("/user/coach/*/schedule") // 教练可约排期 GET /user/coach/{coachId}/schedule
                // === 评价查看（公开只读 GET /user/order/review/{orderId}） ===
                .excludePathPatterns("/user/order/review/*");

        registry.addInterceptor(jwtTokenCoachInterceptor)
                .addPathPatterns("/coach/**")
                .excludePathPatterns("/coach/coach/login")
                .excludePathPatterns("/coach/coach/register");
    }

    /**
     * 接口文档基本信息
     */
    @Bean
    public OpenAPI apiInfo() {
        return new OpenAPI()
                .info(new Info()
                        .title("上门体育项目接口文档")
                        .version("2.0")
                        .description("上门体育项目接口文档"));
    }

    /**
     * 管理端接口分组
     */
    @Bean
    public GroupedOpenApi adminApi() {
        return GroupedOpenApi.builder()
                .group("管理端接口")
                .packagesToScan("com.onsitefitness.controller.admin")
                .build();
    }

    /**
     * 用户端接口分组
     */
    @Bean
    public GroupedOpenApi userApi() {
        return GroupedOpenApi.builder()
                .group("用户端接口")
                .packagesToScan("com.onsitefitness.controller.user")
                .build();
    }

    /**
     * 教练端接口分组
     */
    @Bean
    public GroupedOpenApi coachApi() {
        return GroupedOpenApi.builder()
                .group("教练端接口")
                .packagesToScan("com.onsitefitness.controller.coach")
                .build();
    }

    /**
     * 设置静态资源映射
     * @param registry
     */
    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        registry.addResourceHandler("/upload/**").addResourceLocations("file:upload/");
    }

    /**
     * 扩展消息转换器,比如日期类型转换器等
     * @param converters
     */
    @Override
    public void extendMessageConverters(List<HttpMessageConverter<?>> converters) {
        log.info("开始扩展消息转换器...");
        MappingJackson2HttpMessageConverter converter = new MappingJackson2HttpMessageConverter();
        converter.setObjectMapper(new JacksonObjectMapper());//设置自定义的ObjectMapper
        converters.add(0, converter);     // 将自定义的转换器放在最前面，优先使用自定义的转换器
    }
}

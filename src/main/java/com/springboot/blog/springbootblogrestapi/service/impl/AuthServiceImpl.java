package com.springboot.blog.springbootblogrestapi.service.impl;

import com.springboot.blog.springbootblogrestapi.entity.Role;
import com.springboot.blog.springbootblogrestapi.entity.User;
import com.springboot.blog.springbootblogrestapi.exception.BlogAPIException;
import com.springboot.blog.springbootblogrestapi.payload.LoginDto;
import com.springboot.blog.springbootblogrestapi.payload.RegisterDto;
import com.springboot.blog.springbootblogrestapi.repository.RoleRepository;
import com.springboot.blog.springbootblogrestapi.repository.UserRespository;
import com.springboot.blog.springbootblogrestapi.security.JwtTokenProvider;
import com.springboot.blog.springbootblogrestapi.service.AuthService;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.HashSet;
import java.util.Set;

@Service
public class AuthServiceImpl implements AuthService {

    private AuthenticationManager authenticationManager;
    private UserRespository userRespository;
    private RoleRepository roleRepository;
    private PasswordEncoder passwordEncoder;

    private JwtTokenProvider jwtTokenProvider;

    public AuthServiceImpl(AuthenticationManager authenticationManager,
                           UserRespository userRespository,
                           RoleRepository roleRepository,
                           PasswordEncoder passwordEncoder,
                           JwtTokenProvider jwtTokenProvider) {
        this.authenticationManager = authenticationManager;
        this.userRespository = userRespository;
        this.roleRepository = roleRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @Override
    public String login(LoginDto logindto) {
        Authentication authentication =  authenticationManager.authenticate(new UsernamePasswordAuthenticationToken(
                logindto.getUsernameOrEmail(), logindto.getPassword()));

        SecurityContextHolder.getContext().setAuthentication(authentication);

        String token = jwtTokenProvider.generateToken(authentication);

        return token;
    }

    @Override
    public String register(RegisterDto registerDto) {

        // add check for username exists in the database
        if(userRespository.existsByUsername(registerDto.getUsername())) {
            throw new BlogAPIException(HttpStatus.BAD_REQUEST, "Username is already exists.");
        }

        // add check for email exists in database
        if(userRespository.existsByEmail(registerDto.getEmail())) {
            throw new BlogAPIException(HttpStatus.BAD_REQUEST, "Email is already exists.");
        }

        User user = new User();
        user.setName(registerDto.getName());
        user.setUsername(registerDto.getUsername());
        user.setEmail(registerDto.getEmail());
        user.setPassword(passwordEncoder.encode(registerDto.getPassword()));

        Set<Role> roles = new HashSet<>();
        Role userRole = roleRepository.findByName("ROLE_USER").get();
        roles.add(userRole);
        user.setRoles(roles);

        userRespository.save(user);

        return "User registered successfully";
    }
}

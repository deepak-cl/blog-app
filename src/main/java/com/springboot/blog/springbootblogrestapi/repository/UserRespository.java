package com.springboot.blog.springbootblogrestapi.repository;

import com.springboot.blog.springbootblogrestapi.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface UserRespository extends JpaRepository<User, Long> {

    // Retrieve user by email
    Optional<User> findByEmail(String email);

    // Retrieve user by username or email
    Optional<User> findByUsernameOrEmail(String username, String email);

    // Retrieve user by username or email
    Optional<User> findByUsername(String username);

    // Check if username exists
    Boolean existsByUsername(String username);

    // Check if email exists
    Boolean existsByEmail(String email);
}
